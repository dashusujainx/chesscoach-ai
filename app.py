# app.py

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / "src"))
from retriever import ask
from embedder import collection_exists, get_qdrant_client, setup_user

app = FastAPI(title="ChessCoach AI", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app",
        "https://your-actual-vercel-url.vercel.app"
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track which users are currently being set up
# so we don't run setup twice at the same time
setup_in_progress: set = set()


class QuestionRequest(BaseModel):
    question: str
    username: str


class AnswerResponse(BaseModel):
    answer:   str
    question: str
    username: str


class SetupResponse(BaseModel):
    username:     str
    total_games:  int
    total_chunks: int
    status:       str


@app.get("/")
def health_check():
    return {"status": "ChessCoach AI is running", "version": "2.0.0"}


@app.get("/check/{username}")
def check_user(username: str):
    """
    Check if a user's games are already indexed.
    Frontend calls this first to decide whether to show
    the setup screen or go straight to chat.
    """
    username = username.lower().strip()

    if username in setup_in_progress:
        return {"ready": False, "status": "setup_in_progress"}

    client = get_qdrant_client()
    ready  = collection_exists(client, username)

    # Also check CSV exists
    csv_path = Path("data/processed") / f"{username}_games.csv"
    if ready and csv_path.exists():
        import pandas as pd
        total_games = len(pd.read_csv(csv_path))
        return {"ready": True, "status": "ready", "total_games": total_games}

    return {"ready": False, "status": "not_setup"}


@app.post("/setup/{username}", response_model=SetupResponse)
def setup_username(username: str):
    """
    Fetches, parses, chunks, and embeds games for a new user.
    This takes ~30-60 seconds depending on game count.
    """
    username = username.lower().strip()

    if not username:
        raise HTTPException(status_code=400, detail="Username cannot be empty")

    if username in setup_in_progress:
        raise HTTPException(status_code=409, detail="Setup already in progress for this user")

    setup_in_progress.add(username)

    try:
        result = setup_user(username)
        return SetupResponse(
            username=result["username"],
            total_games=result["total_games"],
            total_chunks=result["total_chunks"],
            status="ready"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Setup failed: {str(e)}")
    finally:
        setup_in_progress.discard(username)


@app.post("/ask", response_model=AnswerResponse)
def ask_question(request: QuestionRequest):
    """
    Main RAG endpoint — answers questions about a user's chess games.
    """
    username = request.username.lower().strip()

    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    # Make sure user is set up
    client = get_qdrant_client()
    if not collection_exists(client, username):
        raise HTTPException(
            status_code=404,
            detail=f"No data found for '{username}'. Call /setup/{username} first."
        )

    answer = ask(request.question, username)
    return AnswerResponse(
        answer=answer,
        question=request.question,
        username=username
    )


@app.get("/suggested-questions")
def suggested_questions():
    return {
        "questions": [
            "Why do I keep losing? What is my biggest weakness?",
            "Which opening should I stop playing?",
            "Do I perform better as White or Black?",
            "What patterns do you see in my endgame losses?",
            "Give me a personalized study plan for this week",
            "Which opponent type do I struggle against most?",
        ]
    }