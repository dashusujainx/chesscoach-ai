# src/fetch_games.py

import requests
import os
import time
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime

load_dotenv()

USERNAME     = os.getenv("CHESSCOM_USERNAME")
RAW_PGN_DIR  = Path("data/raw_pgn")
RAW_PGN_DIR.mkdir(parents=True, exist_ok=True)


def get_available_months(username: str) -> list[dict]:
    """
    Chess.com organizes games by month.
    This endpoint returns every month you have played games.
    Example response: [{"year": 2024, "month": 3}, {"year": 2024, "month": 4}, ...]
    """
    url = f"https://api.chess.com/pub/player/{username}/games/archives"
    
    # Chess.com requires a User-Agent header — without it they block the request
    headers = {"User-Agent": "ChessCoachAI/1.0 contact@chesscoach.dev"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching archives: {response.status_code}")
        return []
    
    # Response looks like: {"archives": ["https://api.chess.com/pub/player/user/games/2024/03", ...]}
    archives = response.json().get("archives", [])
    print(f"Found {len(archives)} months of games")
    return archives


def fetch_month_pgn(archive_url: str) -> str:
    """
    Fetches all games for one specific month as PGN text.
    archive_url looks like: https://api.chess.com/pub/player/user/games/2024/03
    We add /pgn to get PGN format instead of JSON.
    """
    headers = {"User-Agent": "ChessCoachAI/1.0 contact@chesscoach.dev"}
    pgn_url = archive_url + "/pgn"
    
    response = requests.get(pgn_url, headers=headers)
    
    if response.status_code == 200:
        return response.text
    else:
        print(f"  Failed to fetch {pgn_url}: {response.status_code}")
        return ""


def fetch_all_games(username: str, last_n_months: int = 6) -> str:
    """
    Fetches games from the last N months.
    We start with 6 months — enough to find real patterns.
    You can increase this later once everything works.
    """
    print(f"Fetching games for chess.com user: {username}")
    
    archives = get_available_months(username)
    
    if not archives:
        print("No game archives found. Check your username.")
        return ""
    
    # Take the most recent N months
    recent_archives = archives[-last_n_months:]
    print(f"Downloading last {len(recent_archives)} months...")
    
    all_pgn = ""
    
    for archive_url in recent_archives:
        # Extract year/month from URL for display
        parts     = archive_url.split("/")
        year, month = parts[-2], parts[-1]
        print(f"  Fetching {year}/{month}...", end=" ")
        
        pgn = fetch_month_pgn(archive_url)
        game_count = pgn.count("[Event ")
        print(f"{game_count} games")
        
        all_pgn += pgn + "\n"
        
        # Be polite to Chess.com servers — don't hammer them
        time.sleep(0.5)
    
    return all_pgn


def save_games(pgn_text: str, username: str) -> Path:
    output_path = RAW_PGN_DIR / f"{username}_games.pgn"
    output_path.write_text(pgn_text, encoding="utf-8")
    return output_path


# ── Run directly to test ───────────────────────────────────────────────
if __name__ == "__main__":
    
    if not USERNAME:
        print("ERROR: CHESSCOM_USERNAME not set in .env")
        exit(1)
    
    pgn_text = fetch_all_games(USERNAME, last_n_months=6)
    
    if pgn_text:
        path       = save_games(pgn_text, USERNAME)
        total      = pgn_text.count("[Event ")
        print(f"\n✅ Downloaded {total} games → saved to {path}")
        print("\n── Preview ──")
        print(pgn_text[:400])
    else:
        print("❌ No games downloaded. Double-check your username in .env")