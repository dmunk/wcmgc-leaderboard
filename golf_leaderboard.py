#!/usr/bin/env python3
"""
Golf Club Leaderboard Generator

Fetches tournament data from GolfGenius API and generates a leaderboard
based on each player's average of their 5 lowest gross scores in a season.
"""

import os
import requests
import time
import json
from collections import defaultdict
from typing import Dict, List, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
API_KEY = os.getenv("GOLFGENIUS_API_KEY")
BASE_URL = f"https://www.golfgenius.com/api_v2/{API_KEY}" if API_KEY else None
SEASON_YEAR = 2025  # Change this for different seasons
MIN_ROUNDS = 5  # Minimum rounds required to appear on leaderboard

# TODO: This is ugly, but there doesn't seem to be a good way to just identify 
# tournaments in the GolfGenius data that count as posted scores (i.e., not 
# scramble/shamble/match play/senior only). Also the use of tournaments for 
# closest-to-the-pin, long drive, etc. means those must be excluded.
# This list may need to be changed if a tournament format changes, e.g. if 
# the St. Paddy's tournament removes the changing tees making it eligible 
# for gross scoring.
EXCLUDED_EVENTS = ['scramble', 'senior', 'holiday classic', 'member guest', 
                   '3-way', '3 way', '4 club', '4-club', 'president', 
                   'super bowl', '12 man', 'toys for tots', 'match play', 
                   'st. paddy']

def make_api_request(endpoint: str, params: Dict = None) -> Dict:
    """
    Make a GET request to the GolfGenius API.
    
    Args:
        endpoint: API endpoint path (e.g., '/seasons')
        params: Optional dictionary of query parameters
    
    Returns:
        JSON response as a dictionary
    
    Raises:
        requests.exceptions.RequestException: If the API request fails
    """
    if params is None:
        params = {}
    
    # API key is already in the BASE_URL
    url = f"{BASE_URL}{endpoint}"
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raises HTTPError for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making API request to {endpoint}: {e}")
        raise


def extract_from_wrapper(data, key: str):
    """
    Extract data from API response that might be wrapped in a list or dict.
    
    The GolfGenius API sometimes returns data as:
    - A list of dicts with a wrapper key: [{'season': {...}}, {'season': {...}}]
    - A dict with a wrapper key: {'seasons': [...]}
    - Just the data directly
    
    Args:
        data: API response (can be list or dict)
        key: The wrapper key to look for (e.g., 'season', 'event', 'round')
    
    Returns:
        List of extracted items
    """
    if isinstance(data, list):
        # If it's a list, extract the wrapper key from each item
        return [item.get(key, item) for item in data]
    elif isinstance(data, dict):
        # If it's a dict, check for plural key (e.g., 'seasons') or return as single-item list
        plural_key = key + 's'
        if plural_key in data:
            return data[plural_key]
        elif key in data:
            return [data[key]]
        else:
            return [data]
    else:
        return []


def get_season_id(year: int) -> str:
    """
    Get the season ID for a given year.
    
    Args:
        year: The season year (e.g., 2025)
    
    Returns:
        The season ID as a string
    
    Raises:
        ValueError: If the season is not found
    """
    print(f"Fetching season ID for {year}...")
    data = make_api_request('/seasons')
    
    seasons = extract_from_wrapper(data, 'season')
    
    for season in seasons:
        # Match by name containing the year
        season_name = season.get('name', '')
        if str(year) in season_name:
            season_id = season.get('id')
            print(f"Found season: {season_name} (ID: {season_id})")
            return season_id
    
    raise ValueError(f"Season {year} not found in API response")


def get_events(season_id: str) -> List[Dict]:
    """
    Get all events for a given season.
    
    Args:
        season_id: The season ID
    
    Returns:
        List of event dictionaries
    """
    print(f"Fetching events for season {season_id}...")
    data = make_api_request('/events', params={'season': season_id})
    
    events = extract_from_wrapper(data, 'event')
    print(f"Found {len(events)} events")
    return events


def get_event_rounds(event_id: str) -> List[Dict]:
    """
    Get all rounds for a given event.
    
    Args:
        event_id: The event ID
    
    Returns:
        List of round dictionaries
    """
    data = make_api_request(f'/events/{event_id}/rounds')
    return extract_from_wrapper(data, 'round')


def get_tournament_results(event_id: str, round_id: str) -> List[Dict]:
    """
    Get tournament results for a specific event and round.

    Args:
        event_id: The event ID
        round_id: The round ID

    Returns:
        List of player result dictionaries with 'name', 'member_id', and 'gross_score'
    """
    endpoint = f'/events/{event_id}/rounds/{round_id}/tee_sheet'
    
    data = make_api_request(endpoint)
    results = []

    # The data is a list of pairing_group objects
    for item in data:
        pairing_group = item.get('pairing_group', {})
        players = pairing_group.get('players', [])
        
        for player in players:
            member_card_id = player.get('member_card_id')
            player_name = player.get('name')
            score_array = player.get('score_array', [])
            
            # Sum the first 18 scores (ignore holes 19-21 which are extra)
            # Filter out non-numeric values (empty dicts, None, etc.)
            gross_score = sum(
                score for score in score_array[:18] 
                if isinstance(score, (int, float))
            )
            
            # Only add if we have valid data and score is positive
            if member_card_id and player_name and gross_score > 0:
                results.append({
                    'member_id': member_card_id,
                    'name': player_name,
                    'gross_score': gross_score
                })

    return results


def fetch_all_scores(season_id: str) -> Dict[str, Dict]:
    """
    Fetch all scores for all players in a season.
    
    Args:
        season_id: The season ID
    
    Returns:
        Dictionary mapping member_id to player info with scores
        Format: {
            'member_id': {
                'name': 'John Doe',
                'scores': [72, 75, 68, ...]
            }
        }
    """
    player_data = defaultdict(lambda: {'name': '', 'scores': []})
    
    # Get all events for the season
    events = get_events(season_id)
    
    for event in events:
        event_id = event.get('id')
        event_name = event.get('name', '')

        event_excluded = False

        if any(excluded in event_name.lower() for excluded in EXCLUDED_EVENTS):
            event_excluded = True

        if not event_excluded:
            print(f"\nProcessing event: {event_name}")
            
            # Get rounds for this event
            rounds = get_event_rounds(event_id)
            print(f"  Found {len(rounds)} rounds")
            
            for round_data in rounds:
                # Special handling: Club Championship Qualifier seems to contain both the qualifying round and 
                # subsequent rounds of the actual tournament. We only want to count the qualifier.

                round_id = round_data.get('id')
                round_name = round_data.get('name')
                
                exclude_round = False

                if 'Scratch Qualifier' in event_name and 'Qualifying' not in round_name:
                    exclude_round = True

                if not exclude_round:
                    try:
                        # Get results
                        results = get_tournament_results(event_id, round_id)

                        # Only process if we got results with gross scores
                        if results:
                            print(f"  Retrieved scores for {len(results)} players in round {round_id}")
                            
                            # Store scores by player
                            for result in results:
                                if (result['gross_score'] > 0):
                                    name = result['name']
                                    player_data[name]['name'] = result['name']
                                    player_data[name]['scores'].append(result['gross_score'])
                        
                    except AttributeError as e:
                        print(f"  Warning: AttributeError for round {round_id}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                    except Exception as e:
                        print(f"  Warning: Could not get results for round {round_id}: {e}")
                        continue
                        
                        # Small delay to avoid hammering the API
                        time.sleep(0.3)
                        
                    except Exception as e:
                        print(f"  Error processing round {round_id}: {e}")
                        continue
    
    return dict(player_data)


def calculate_leaderboard(player_data: Dict[str, Dict], min_rounds: int = MIN_ROUNDS) -> List[Tuple]:
    """
    Calculate leaderboard from player data.
    
    Args:
        player_data: Dictionary of player data with scores
        min_rounds: Minimum number of rounds required to qualify
    
    Returns:
        Sorted list of tuples: (name, avg_of_best_5, num_rounds, best_5_scores)
    """
    leaderboard = []

    for member_id, data in player_data.items():
        scores = data['scores']
        num_rounds = len(scores)
        
        # Skip players with fewer than minimum rounds
        if num_rounds < min_rounds:
            continue
        
        # Get the 5 lowest scores
        best_5 = sorted(scores)[:5]
        avg_best_5 = sum(best_5) / len(best_5)
        
        leaderboard.append((
            data['name'],
            avg_best_5,
            num_rounds,
            best_5
        ))
    
    # Sort by average (lowest first)
    leaderboard.sort(key=lambda x: x[1])
    
    return leaderboard


def print_leaderboard(leaderboard: List[Tuple]):
    """
    Print the leaderboard in a formatted table.
    
    Args:
        leaderboard: Sorted leaderboard data
    """
    print("\n" + "="*80)
    print("GOLF CLUB LEADERBOARD - BEST 5 ROUND AVERAGE")
    print("="*80)
    print(f"{'Rank':<6} {'Player Name':<30} {'Avg':<8} {'Rounds':<8} {'Best 5 Scores'}")
    print("-"*80)
    
    for rank, (name, avg, num_rounds, best_5) in enumerate(leaderboard, 1):
        scores_str = ", ".join(str(int(s)) for s in best_5)
        print(f"{rank:<6} {name:<30} {avg:.2f}   {num_rounds:<8} {scores_str}")
    
    print("="*80)
    print(f"Total players qualifying: {len(leaderboard)}")


def main():
    """Main execution function."""
    # Validate API key is set
    if not API_KEY:
        print("Error: GOLFGENIUS_API_KEY environment variable not set.")
        print("Please create a .env file with your API key (see README.md)")
        return
    
    print(f"Starting leaderboard generation for {SEASON_YEAR} season...")
    print(f"Minimum rounds required: {MIN_ROUNDS}\n")
    
    try:
        # Step 1: Get season ID
        season_id = get_season_id(SEASON_YEAR)
        
        # Step 2: Fetch all scores
        player_data = fetch_all_scores(season_id)
        print(f"\nTotal players found: {len(player_data)}")
        
        # Step 3: Calculate leaderboard
        leaderboard = calculate_leaderboard(player_data)
        
        # Step 4: Display results
        print_leaderboard(leaderboard)
        
    except Exception as e:
        print(f"\nError generating leaderboard: {e}")
        raise


if __name__ == "__main__":
    main()