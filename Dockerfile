# ── Stage 1: Builder ──────────────────────────────────────────
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (better layer caching)
COPY pyproject.toml .
COPY uv.lock* .

# Install dependencies into /app/.venv
RUN uv sync --frozen --no-dev

# ── Stage 2: Runtime ──────────────────────────────────────────
FROM python:3.13-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code only — NO data/
COPY app.py .
COPY src/ ./src/

# Create empty data dirs — filled at runtime per user
RUN mkdir -p data/raw_pgn data/processed

# Make sure .venv binaries are on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Pre-download the embedding model at build time
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

# Expose FastAPI port
EXPOSE 8000

# Start the server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]