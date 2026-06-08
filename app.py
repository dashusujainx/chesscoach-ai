# app.py
# FastAPI backend — the bridge between Next.js UI and RAG pipeline

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / "src"))
from retriever import ask

app = FastAPI(title="ChessCoach AI", version="1.0.0")

# Allow Next.js (port 3000) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


class AnswerResponse(BaseModel):
    answer: str
    question: str


@app.get("/")
def health_check():
    return {"status": "ChessCoach AI is running"}


@app.post("/ask", response_model=AnswerResponse)
def ask_question(request: QuestionRequest):
    """
    Main endpoint — receives a question from the UI,
    runs the full RAG pipeline, returns the answer.
    """
    answer = ask(request.question)
    return AnswerResponse(
        answer=answer,
        question=request.question
    )


@app.get("/suggested-questions")
def suggested_questions():
    """Returns suggested questions for the UI."""
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