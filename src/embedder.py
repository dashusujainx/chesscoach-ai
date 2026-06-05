# src/embedder.py
#
# WHAT THIS FILE DOES:
# Takes our 755 text chunks and:
# 1. Converts each chunk into a vector (list of numbers)
#    using fastembed — a free local embedding model
# 2. Stores all vectors in Qdrant — our vector database
#
# WHY VECTORS?
# Computers can't search text by meaning — only exact words.
# Vectors solve this. "I lost the endgame" and "checkmate in
# the final phase" will have SIMILAR vectors even though the
# words are different. That's semantic search.
#
# EXAMPLE:
# "Why do I blunder in endgames?" 
# → converts to a vector
# → finds the 5 most similar endgame chunk vectors
# → returns those chunks to the LLM as context

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct
)
from fastembed import TextEmbedding
import pandas as pd
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv

# import our chunker from Phase 2
import sys
sys.path.append(str(Path(__file__).parent))
from chunker import chunk_all_games

load_dotenv()

USERNAME  = os.getenv("CHESSCOM_USERNAME")
PROCESSED = Path("data/processed")

# ── Config ─────────────────────────────────────────────────────────────
COLLECTION_NAME = "chess_games"   # name of our Qdrant collection
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"  # free, fast, good quality
# This model produces 384-dimensional vectors


def get_qdrant_client():
    return QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )


def get_embedding_model() -> TextEmbedding:
    """
    Loads the embedding model.
    First run downloads ~130MB — subsequent runs use the cache.
    """
    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    print("(First run downloads ~130MB — wait for it...)")
    return TextEmbedding(EMBEDDING_MODEL)


def create_collection(client: QdrantClient):
    """
    Creates the Qdrant collection if it doesn't exist.
    A collection is like a table in a database — but for vectors.
    
    size=384 must match the embedding model's output dimensions.
    Distance.COSINE measures similarity between vectors (0=different, 1=identical).
    """
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME in existing:
        print(f"Collection '{COLLECTION_NAME}' already exists — deleting and recreating")
        client.delete_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=384,              # must match BAAI/bge-small-en-v1.5 output
            distance=Distance.COSINE
        )
    )
    print(f"Created collection: {COLLECTION_NAME}")


def embed_and_store(chunks: list[dict], client: QdrantClient, model: TextEmbedding):
    """
    The core function — embeds all chunks and stores them in Qdrant.
    
    Each stored point has:
    - id:      unique identifier
    - vector:  the embedding (384 numbers)
    - payload: the original text + metadata (phase, result, opening, etc.)
    """
    print(f"\nEmbedding {len(chunks)} chunks...")
    print("This may take 1-2 minutes on first run...")

    # Extract just the text from each chunk for embedding
    texts = [chunk["text"] for chunk in chunks]

    # Generate embeddings for all texts at once (batched = faster)
    embeddings = list(model.embed(texts))
    print(f"Generated {len(embeddings)} embeddings")

    # Build Qdrant points — each point = vector + metadata
    points = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        point = PointStruct(
            id=str(uuid.uuid4()),   # unique ID for each chunk
            vector=embedding.tolist(),
            payload={
                "text":         chunk["text"],
                "phase":        chunk["phase"],
                "result":       chunk["result"],
                "opening":      chunk["opening"],
                "played_as":    chunk["played_as"],
                "my_rating":    chunk["my_rating"],
                "opp_rating":   chunk["opp_rating"],
                "date":         chunk["date"],
                "termination":  chunk["termination"],
                "total_moves":  chunk["total_moves"],
                "time_control": chunk["time_control"],
            }
        )
        points.append(point)

    # Upload all points to Qdrant in batches of 100
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=batch
        )
        print(f"  Stored {min(i + batch_size, len(points))}/{len(points)} chunks...")

    print(f"\nAll {len(points)} chunks stored in Qdrant!")


def verify_storage(client: QdrantClient):
    """
    Confirms everything was stored correctly.
    Also does a test search to make sure retrieval works.
    """
    count = client.count(collection_name=COLLECTION_NAME).count
    print(f"\nVerification: {count} vectors in Qdrant")

    # Test search — find chunks related to losing
    print("\nTest search: 'games where I lost in the endgame'")
    model     = TextEmbedding(EMBEDDING_MODEL)
    query_vec = list(model.embed(["games where I lost in the endgame"]))[0]

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec.tolist(),
        limit=3
    ).points

    print(f"Top 3 most relevant chunks found:")
    for i, r in enumerate(results):
        print(f"\n  Result {i+1} (score: {r.score:.3f})")
        print(f"  Phase:   {r.payload['phase']}")
        print(f"  Result:  {r.payload['result']}")
        print(f"  Opening: {r.payload['opening']}")
        print(f"  Date:    {r.payload['date']}")


# ── Run directly ───────────────────────────────────────────────────────
if __name__ == "__main__":
    csv_path = PROCESSED / f"{USERNAME}_games.csv"

    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found. Run parse_pgn.py first.")
        exit(1)

    # Step 1: Load chunks from Phase 2
    print("Step 1: Loading chunks...")
    chunks = chunk_all_games(csv_path)

    # Step 2: Connect to Qdrant (local, no server needed)
    print("\nStep 2: Connecting to Qdrant...")
    client = get_qdrant_client()

    # Step 3: Create the collection
    print("\nStep 3: Creating collection...")
    create_collection(client)

    # Step 4: Load embedding model
    print("\nStep 4: Loading embedding model...")
    model = get_embedding_model()

    # Step 5: Embed everything and store in Qdrant
    print("\nStep 5: Embedding and storing...")
    embed_and_store(chunks, client, model)

    # Step 6: Verify it all worked
    print("\nStep 6: Verifying storage...")
    verify_storage(client)

    print("\n✅ Phase 3 complete! Your chess games are now searchable by meaning.")
    print("   Next step: retriever.py + Groq LLM = ask questions about your games!")