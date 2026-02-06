#!/usr/bin/env python3
"""
Golf Club Leaderboard Generator

Fetches tournament data from GolfGenius API and generates a leaderboard
based on each player's average of their 5 lowest gross scores in a season.
"""

import os
import requests
import time
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


def get_tournament_ids(event_id: str, round_id: str) -> List[str]:
    """
    Get all tournament IDs for a given event and round.
    
    Args:
        event_id: The event ID
        round_id: The round ID
    
    Returns:
        List of tournament IDs
    """
    data = make_api_request(f'/events/{event_id}/rounds/{round_id}/tournaments')
    
    tournaments = extract_from_wrapper(data, 'tournament')
    
    tournament_ids = []
    for tournament in tournaments:
        # The tournament_id is in the 'event' object's 'id' field
        tournament_id = tournament.get('event', {}).get('id')
        if tournament_id:
            tournament_ids.append(tournament_id)
    
    return tournament_ids


def get_tournament_results(event_id: str, round_id: str, tournament_id: str) -> List[Dict]:
    """
    Get tournament results for a specific event, round, and tournament.
    
    Args:
        event_id: The event ID
        round_id: The round ID
        tournament_id: The tournament ID
    
    Returns:
        List of player result dictionaries with 'name', 'member_id', and 'gross_score'
    """
    endpoint = f'/events/{event_id}/rounds/{round_id}/tournaments/{tournament_id}.json'
    data = make_api_request(endpoint)
    
    results = []
    
    # Extract event data using helper
    events = extract_from_wrapper(data, 'event')
    event_data = events[0] if events else {}
    
    scopes = event_data.get('scopes', [])
    
    for scope in scopes:
        aggregates = scope.get('aggregates', {})
        
        # Handle aggregates being either a dict or a list
        if isinstance(aggregates, list):
            # If it's a list, look through each aggregate
            for aggregate in aggregates:
                individual_results = aggregate.get('individual_results', [])
                results.extend(_extract_player_results(individual_results))
        else:
            # If it's a dict, process normally
            individual_results = aggregates.get('individual_results', [])
            results.extend(_extract_player_results(individual_results))
    
    return results


def _extract_player_results(individual_results: List[Dict]) -> List[Dict]:
    """
    Helper function to extract player results from individual_results list.
    
    Args:
        individual_results: List of player result data
    
    Returns:
        List of player result dictionaries with 'name', 'member_id', and 'gross_score'
    """
    results = []
    for player in individual_results:
        member_id = player.get('member_id')
        member_name = player.get('name')

        # Get the gross score
        totals = player.get('totals', {})
        gross_scores = totals.get('gross_scores', {})
        gross_score = gross_scores.get('total')

        # Only add if we have valid data
        if member_id and member_name and gross_score is not None:
            results.append({
                'member_id': member_id,
                'name': member_name,
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
        print(f"\nProcessing event: {event_name}")
        
        # Get rounds for this event
        rounds = get_event_rounds(event_id)
        print(f"  Found {len(rounds)} rounds")
        
        for round_data in rounds:
            round_id = round_data.get('id')
            
            try:
                # Get all tournament IDs for this event/round
                tournament_ids = get_tournament_ids(event_id, round_id)
                print(f"  Found {len(tournament_ids)} tournaments for round")
                
                # Loop through all tournaments
                for tournament_id in tournament_ids:
                    try:
                        # Get results
                        results = get_tournament_results(event_id, round_id, tournament_id)
                        
                        # Only process if we got results with gross scores
                        if results:
                            print(f"  Retrieved scores for {len(results)} players in tournament {tournament_id}")
                            
                            # Store scores by player
                            for result in results:
                                member_id = result['member_id']
                                player_data[member_id]['name'] = result['name']
                                player_data[member_id]['scores'].append(result['gross_score'])
                        
                    except AttributeError as e:
                        print(f"  Warning: AttributeError for tournament {tournament_id}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                    except Exception as e:
                        print(f"  Warning: Could not get results for tournament {tournament_id}: {e}")
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
    print(player_data)
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