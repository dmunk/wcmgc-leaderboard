# Golf Club Leaderboard Generator

Generates a leaderboard based on each player's average of their 5 lowest gross scores in a season using data from the GolfGenius API.

## Setup

1. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your API key**:
   ```bash
   # Copy the example environment file
   cp .env.example .env
   
   # Edit .env and add your actual API key
   # GOLFGENIUS_API_KEY=your_actual_api_key_here
   ```
   
   The `.env` file is in `.gitignore` and won't be committed to version control.

4. **Optionally adjust settings** in `golf_leaderboard.py`:
   - `SEASON_YEAR`: The season year to analyze (default: 2025)
   - `MIN_ROUNDS`: Minimum rounds required to qualify (default: 5)

## Usage

Run the script:
```bash
python golf_leaderboard.py
```

The script will:
1. Fetch the season ID for the specified year
2. Retrieve all events and tournaments for that season
3. Collect gross scores for each player
4. Calculate the average of each player's 5 best scores
5. Display a sorted leaderboard

## Configuration Options

Edit the `.env` file for sensitive configuration:
- `GOLFGENIUS_API_KEY`: Your GolfGenius API key

Edit these constants at the top of `golf_leaderboard.py`:
- `SEASON_YEAR`: The season year to analyze (default: 2025)
- `MIN_ROUNDS`: Minimum rounds required to qualify (default: 5)

## How It Works

The script navigates the GolfGenius API hierarchy:
1. **Seasons** → Get the season ID for the year
2. **Events** → Get all tournaments in the season
3. **Rounds** → Get rounds for each event
4. **Tournaments** → Get tournament IDs (matches event name)
5. **Results** → Extract gross scores for each player

All data is stored in memory using a dictionary structure, with no database required.

## Output

The leaderboard displays:
- Player rank
- Player name
- Average of best 5 scores
- Total rounds played
- The 5 best scores used in the calculation

Players with fewer than 5 rounds are excluded from the leaderboard.

## Future Automation

To automate this report:

**Linux/Mac (cron)**:
```bash
# Edit crontab
crontab -e

# Add a line to run weekly on Mondays at 9 AM
0 9 * * 1 /path/to/venv/bin/python /path/to/golf_leaderboard.py > /path/to/leaderboard.log 2>&1
```

**Windows (Task Scheduler)**:
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., weekly)
4. Action: Start a program
5. Program: `C:\path\to\venv\Scripts\python.exe`
6. Arguments: `C:\path\to\golf_leaderboard.py`

## Troubleshooting

**"GOLFGENIUS_API_KEY environment variable not set"**: Make sure you've created a `.env` file (copy from `.env.example`) and added your API key

**API Key Issues**: Verify your API key works by testing it in the GolfGenius API console

**Season Not Found**: Check that the season name in GolfGenius matches the year format you're searching for

**Missing Scores**: The script skips rounds that encounter errors and continues processing

**Rate Limiting**: The script includes a 0.3 second delay between API calls to avoid overwhelming the server
