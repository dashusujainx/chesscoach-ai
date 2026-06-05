# src/parse_pgn.py
#
# WHAT THIS FILE DOES:
# Reads the raw .pgn file and extracts structured, meaningful
# information from each game — things like:
#   - Did you win or lose?
#   - What opening did you play?
#   - How accurate were you?
#   - How many moves did the game last?
#
# This turns raw chess notation into data we can actually analyze.

import chess.pgn          # reads PGN format game by game
import pandas as pd       # for organizing data into a table
import os
from pathlib import Path
from dotenv import load_dotenv
import io                 # for reading strings as files

load_dotenv()

USERNAME    = os.getenv("CHESSCOM_USERNAME")
RAW_PGN_DIR = Path("data/raw_pgn")
PROCESSED   = Path("data/processed")
PROCESSED.mkdir(parents=True, exist_ok=True)


def parse_result(result_str: str, played_as: str) -> str:
    """
    Converts PGN result like "1-0" into "win", "loss", or "draw"
    from YOUR perspective.

    result_str: "1-0" (white won), "0-1" (black won), "1/2-1/2" (draw)
    played_as:  "white" or "black"
    """
    if result_str == "1/2-1/2":
        return "draw"
    if played_as == "white":
        return "win" if result_str == "1-0" else "loss"
    else:
        return "win" if result_str == "0-1" else "loss"


def get_phase_moves(game) -> dict:
    """
    Splits the game into 3 phases and returns the moves for each.
    
    Opening:    moves 1-10
    Middlegame: moves 11-30  
    Endgame:    moves 31+
    
    Why split? Because your weakness might be SPECIFIC to one phase.
    Maybe you play openings well but blunder in endgames.
    """
    board      = game.board()
    all_moves  = []

    for move in game.mainline_moves():
        all_moves.append(board.san(move))  # SAN = standard algebraic notation e.g. "e4"
        board.push(move)

    total = len(all_moves)

    return {
        "opening_moves":     " ".join(all_moves[:10]),
        "middlegame_moves":  " ".join(all_moves[10:30]),
        "endgame_moves":     " ".join(all_moves[30:]),
        "total_moves":       total,
    }


def extract_game_data(game, username: str) -> dict:
    """
    Extracts everything useful from one chess game object.
    Returns a flat dictionary — one row in our final dataset.
    """
    headers = game.headers  # metadata like [White "..."] [Result "1-0"] etc.

    white   = headers.get("White", "").lower()
    black   = headers.get("Black", "").lower()
    user_lc = username.lower()

    # Figure out which color you played
    played_as = "white" if white == user_lc else "black"

    result_str = headers.get("Result", "*")
    result     = parse_result(result_str, played_as)

    # Opening name — Chess.com includes this as "ECOUrl" header
    eco_url = headers.get("ECOUrl", "")
    opening = eco_url.split("/")[-1].replace("-", " ") if eco_url else "Unknown"

    # Your rating and opponent rating for this game
    my_rating  = int(headers.get("WhiteElo", 0) if played_as == "white" else headers.get("BlackElo", 0))
    opp_rating = int(headers.get("BlackElo", 0) if played_as == "white" else headers.get("WhiteElo", 0))

    # Accuracy — Chess.com includes this in PGN headers
    my_acc  = headers.get("WhiteAccuracy", None) if played_as == "white" else headers.get("BlackAccuracy", None)
    opp_acc = headers.get("BlackAccuracy", None) if played_as == "white" else headers.get("WhiteAccuracy", None)

    # Game type — blitz, rapid, bullet
    time_control = headers.get("TimeControl", "unknown")

    # Termination reason — "checkmate", "resignation", "time forfeit" etc.
    termination = headers.get("Termination", "unknown")

    # Get phase-level moves
    phases = get_phase_moves(game)

    return {
        "date":             headers.get("Date", ""),
        "played_as":        played_as,
        "result":           result,
        "opening":          opening,
        "eco":              headers.get("ECO", ""),
        "my_rating":        my_rating,
        "opponent":         black if played_as == "white" else white,
        "opp_rating":       opp_rating,
        "my_accuracy":      float(my_acc)  if my_acc  else None,
        "opp_accuracy":     float(opp_acc) if opp_acc else None,
        "time_control":     time_control,
        "termination":      termination,
        **phases,           # unpacks opening_moves, middlegame_moves, endgame_moves, total_moves
    }


def parse_pgn_file(pgn_path: Path, username: str) -> pd.DataFrame:
    """
    Reads the entire .pgn file and converts it into a pandas DataFrame.
    Each row = one game.
    """
    print(f"Parsing {pgn_path} ...")
    pgn_text = pgn_path.read_text(encoding="utf-8")

    games_data = []
    pgn_io     = io.StringIO(pgn_text)   # treat the string like a file
    game_num   = 0

    while True:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break  # no more games

        try:
            data = extract_game_data(game, username)
            games_data.append(data)
            game_num += 1

            if game_num % 50 == 0:
                print(f"  Parsed {game_num} games...")

        except Exception as e:
            print(f"  Skipped game {game_num}: {e}")
            continue

    print(f"Done! Parsed {len(games_data)} games total.")
    return pd.DataFrame(games_data)


def show_quick_stats(df: pd.DataFrame):
    """
    Prints a quick summary of your chess performance.
    This is a preview of the pattern analysis we'll do in Phase 4.
    """
    print("\n" + "="*50)
    print("YOUR CHESS STATS SUMMARY")
    print("="*50)

    total = len(df)
    wins  = len(df[df["result"] == "win"])
    draws = len(df[df["result"] == "draw"])
    print(f"Total games : {total}")
    print(f"Wins        : {wins}  ({100*wins//total}%)")
    print(f"Draws       : {draws} ({100*draws//total}%)")
    print(f"Losses      : {total-wins-draws} ({100*(total-wins-draws)//total}%)")

    print(f"\nAs White    : {len(df[df['played_as']=='white'])} games")
    print(f"As Black    : {len(df[df['played_as']=='black'])} games")

    print(f"\nAvg accuracy: {df['my_accuracy'].mean():.1f}%")
    print(f"Avg moves/game: {df['total_moves'].mean():.1f}")

    print(f"\nTop 5 openings you play:")
    top_openings = df["opening"].value_counts().head(5)
    for opening, count in top_openings.items():
        subset  = df[df["opening"] == opening]
        winrate = len(subset[subset["result"] == "win"]) * 100 // len(subset)
        print(f"  {opening[:45]:<45} {count} games  {winrate}% wins")


# ── Run directly ────────────────────────────────────────────────────
if __name__ == "__main__":
    pgn_path = RAW_PGN_DIR / f"{USERNAME}_games.pgn"

    if not pgn_path.exists():
        print(f"ERROR: {pgn_path} not found. Run fetch_games.py first.")
        exit(1)

    df = parse_pgn_file(pgn_path, USERNAME)

    # Save as CSV — easy to inspect and use in later phases
    csv_path = PROCESSED / f"{USERNAME}_games.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nSaved structured data → {csv_path}")

    # Show a quick performance summary
    show_quick_stats(df)