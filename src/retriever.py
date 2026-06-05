# src/retriever.py
#
# THIS IS THE PAYOFF FILE.
# You ask a question in plain English.
# It searches your 755 game vectors for relevant context.
# It sends that context to Groq LLM.
# You get a personalized, specific answer about YOUR chess.
#
# This is the complete RAG pipeline in one file.

from qdrant_client import QdrantClient
from fastembed import TextEmbedding
from groq import Groq
import os
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd

load_dotenv()


ROUTE_AGGREGATE = "aggregate"
ROUTE_SPECIFIC  = "specific"
ROUTE_HYBRID    = "hybrid"

GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
USERNAME        = os.getenv("CHESSCOM_USERNAME")
COLLECTION_NAME = "chess_games"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
PROCESSED = Path("data/processed")


def get_aggregate_stats() -> str:
    """
    For aggregate questions, read directly from CSV.
    This is more accurate than retrieving chunks.
    """
    csv_path = PROCESSED / f"{USERNAME}_games.csv"
    df = pd.read_csv(csv_path)

    total  = len(df)
    wins   = len(df[df["result"] == "win"])
    losses = len(df[df["result"] == "loss"])
    draws  = len(df[df["result"] == "draw"])

    white_df   = df[df["played_as"] == "white"]
    black_df   = df[df["played_as"] == "black"]
    white_wins = len(white_df[white_df["result"] == "win"])
    black_wins = len(black_df[black_df["result"] == "win"])

    top_openings = df.groupby("opening").agg(
        games=("result", "count"),
        wins=("result", lambda x: (x == "win").sum())
    ).sort_values("games", ascending=False).head(8)

    top_openings["win_rate"] = (top_openings["wins"] / top_openings["games"] * 100).round(1)

    openings_text = "\n".join([
        f"  {row.Index[:40]}: {row.games} games, {row.win_rate}% wins"
        for row in top_openings.itertuples()
    ])

    return f"""FULL GAME STATISTICS (all {total} games):
Wins: {wins} ({100*wins//total}%)
Losses: {losses} ({100*losses//total}%)
Draws: {draws} ({100*draws//total}%)

As White: {len(white_df)} games, {white_wins} wins ({100*white_wins//len(white_df)}%)
As Black: {len(black_df)} games, {black_wins} wins ({100*black_wins//len(black_df)}%)

Top openings by games played:
{openings_text}"""


def get_clients():
    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )
    embed  = TextEmbedding(EMBEDDING_MODEL)
    groq   = Groq(api_key=GROQ_API_KEY)
    return qdrant, embed, groq


def retrieve_relevant_chunks(
    question: str,
    qdrant: QdrantClient,
    embed_model: TextEmbedding,
    limit: int = 8
) -> list[dict]:
    """
    Step 1 of RAG: Retrieve
    
    Converts the question to a vector and finds the
    most semantically similar chunks from your game history.
    
    limit=8 means we fetch the 8 most relevant game moments.
    More context = better answer, but too much = LLM gets confused.
    8 is a good balance.
    """
    # Convert question to vector
    query_vector = list(embed_model.embed([question]))[0]

    # Search Qdrant for most similar chunks
    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector.tolist(),
        limit=limit
    ).points

    # Extract payload from each result
    return [r.payload for r in results]


def build_context(chunks: list[dict]) -> str:
    """
    Formats retrieved chunks into a readable context block
    that the LLM can understand and reason about.
    """
    context_parts = []

    for i, chunk in enumerate(chunks, 1):
        context_parts.append(f"""
Game {i}:
{chunk['text']}
---""")

    return "\n".join(context_parts)

def ask_groq(
    question: str,
    context: str,
    groq_client: Groq
) -> str:
    system_prompt = f"""You are ChessCoach AI — a personalized chess improvement assistant.

You have been given real game data from {USERNAME}'s chess history on Chess.com.
Each game shows the phase (opening/middlegame/endgame), result (win/loss/draw),
opening name, rating, and moves played.

Your job:
- Analyze ONLY the game data provided below — never reference games not shown
- Never say "Game 1", "Game 2" etc — you don't have numbered games, only chunks
- Mention specific openings, dates, and results you can see in the context
- Never invent statistics or games not present in the retrieved chunks
- If you only see a few games in context, say "based on the games I can see" — never extrapolate
- Never mention an opening name unless it appears explicitly in the context below
- If you cannot answer confidently from the context, say so honestly
- NEVER mention a specific game, move, or opening that is not explicitly written in the context below. If it is not there, do not say it.
- When OVERALL STATISTICS are provided, use ONLY those for win rates and opening names. NEVER mix opening names from SPECIFIC RELEVANT GAMES into statistical claims.
- Be direct and actionable — tell them exactly what to work on
- Keep your answer concise (150-200 words max)

Remember: You are analyzing REAL games from their history, not hypothetical scenarios."""

    user_message = f"""Here are the most relevant games from my chess history:

{context}

My question: {question}

IMPORTANT: Only reference openings and games explicitly shown above. Do not invent or extrapolate."""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message}
        ],
        temperature=0.1,
        max_tokens=500
    )

    return response.choices[0].message.content


def ask(question: str) -> str:
    """
    Modern agentic RAG — routes question to the right tool first.
    
    aggregate → CSV stats only (all games from CSV)
    specific  → vector search only (relevant chunks)
    hybrid    → both combined
    """
    from router import classify_question, rewrite_query

    qdrant, embed_model, groq_client = get_clients()

    # Step 1: Classify the question
    route = classify_question(question, groq_client)
    print(f"Route: {route}")

    stats   = ""
    context = ""
    total_games = 0

    # Step 2: Call the right tool based on route
    if route == ROUTE_AGGREGATE or route == ROUTE_HYBRID:
        stats = get_aggregate_stats()
        csv_path = PROCESSED / f"{USERNAME}_games.csv"
        total_games = len(pd.read_csv(csv_path))
        print("Used: CSV aggregate stats")

    if route == ROUTE_SPECIFIC or route == ROUTE_HYBRID:
        search_query = rewrite_query(question, groq_client)
        chunks  = retrieve_relevant_chunks(search_query, qdrant, embed_model, limit=4)
        context = build_context(chunks)
        print("Used: vector search with rewritten query")

    # Step 3: Build full context
    parts = []
    if stats:
        parts.append(f"=== OVERALL STATISTICS (all {total_games} games) ===\n{stats}")
    if context:
        parts.append(f"=== SPECIFIC RELEVANT GAMES (examples only — do NOT use opening names from here for statistics) ===\n{context}")

    full_context = "\n\n".join(parts)

    # Step 4: Generate answer
    answer = ask_groq(question, full_context, groq_client)
    return answer


# ── Run directly to test with real questions ───────────────────────────
if __name__ == "__main__":

    # These are the questions ChessCoach AI can now answer
    # about YOUR real games — try changing them!
    test_questions = [
        "Why do I keep losing? What is my biggest weakness?",
        "Which opening should I stop playing based on my results?",
        "Do I perform better as White or Black and why?",
    ]

    for question in test_questions:
        print("=" * 60)
        print(f"QUESTION: {question}")
        print("=" * 60)
        answer = ask(question)
        print(answer)
        print()