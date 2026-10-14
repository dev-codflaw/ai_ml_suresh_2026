"""Vector-store access for PostgreSQL/pgvector or MongoDB Atlas."""

import os
import re
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from db import get_connection


load_dotenv(Path(__file__).with_name(".env"))

VECTOR_STORE = os.getenv("VECTOR_STORE", "postgres").strip().lower()
MONGODB_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI", "")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "ai_ml_vectordb")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "vector_embeddings")
POSTGRES_TABLE = os.getenv("POSTGRES_TABLE", "vector_embeddings").strip()
MONGODB_INDEX_NAME = os.getenv("MONGODB_INDEX_NAME", "vector_index")
MONGODB_SERVER_SELECTION_TIMEOUT_MS = int(
    os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "30000")
)
MONGODB_CONNECT_TIMEOUT_MS = int(os.getenv("MONGODB_CONNECT_TIMEOUT_MS", "10000"))
EMBEDDING_DIMENSIONS = 384

if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", POSTGRES_TABLE):
    raise ValueError("POSTGRES_TABLE must be a valid PostgreSQL table name.")


def _uses_mongodb() -> bool:
    return VECTOR_STORE in {"mongo", "mongodb", "mongodb-atlas"}


def get_vector_store_label() -> str:
    """Return a short, user-facing name for the configured vector store."""
    if _uses_mongodb():
        return f"MongoDB Atlas Vector Search ({MONGODB_DATABASE}.{MONGODB_COLLECTION})"
    return "PostgreSQL + pgvector"


@lru_cache(maxsize=1)
def _get_mongodb_collection():
    """Connect once to MongoDB Atlas and return the chunks collection."""
    if not MONGODB_URI:
        raise RuntimeError(
            "MONGODB_URI is required when VECTOR_STORE=mongodb. "
            "Add your MongoDB Atlas connection string to .env."
        )

    try:
        from pymongo import MongoClient
    except ImportError as error:
        raise RuntimeError(
            "MongoDB support requires pymongo. Run: pip install pymongo"
        ) from error

    client = MongoClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=MONGODB_SERVER_SELECTION_TIMEOUT_MS,
        connectTimeoutMS=MONGODB_CONNECT_TIMEOUT_MS,
    )
    client.admin.command("ping")
    return client[MONGODB_DATABASE][MONGODB_COLLECTION]


def _ensure_mongodb_index() -> None:
    """Create the Atlas vector index if it does not exist yet."""
    collection = _get_mongodb_collection()
    try:
        from pymongo.operations import SearchIndexModel

        existing_names = {
            index["name"] for index in collection.list_search_indexes()
        }
        if MONGODB_INDEX_NAME in existing_names:
            return

        collection.create_search_index(
            model=SearchIndexModel(
                definition={
                    "fields": [
                        {
                            "type": "vector",
                            "numDimensions": EMBEDDING_DIMENSIONS,
                            "path": "embedding",
                            "similarity": "cosine",
                        }
                    ]
                },
                name=MONGODB_INDEX_NAME,
                type="vectorSearch",
            )
        )
    except Exception as error:
        raise RuntimeError(
            "Could not create or inspect the MongoDB Atlas vector index "
            f"'{MONGODB_INDEX_NAME}'. Check Atlas permissions and Vector Search "
            f"availability: {error}"
        ) from error


def create_table() -> None:
    """Create the selected vector store's table/collection and index."""
    if _uses_mongodb():
        _ensure_mongodb_index()
        return

    sql = f"""
        CREATE EXTENSION IF NOT EXISTS vector;

        CREATE TABLE IF NOT EXISTS {POSTGRES_TABLE} (
            id SERIAL PRIMARY KEY,
            source TEXT NOT NULL,
            document_name TEXT NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding vector(384) NOT NULL
        );

        ALTER TABLE {POSTGRES_TABLE}
            ADD COLUMN IF NOT EXISTS source TEXT;

        ALTER TABLE {POSTGRES_TABLE}
            ADD COLUMN IF NOT EXISTS document_name TEXT;

        ALTER TABLE {POSTGRES_TABLE}
            ADD COLUMN IF NOT EXISTS chunk_text TEXT;

        ALTER TABLE {POSTGRES_TABLE}
            ADD COLUMN IF NOT EXISTS embedding vector(384);
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)


def save_chunks(
    document_name: str,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    """Save all chunks for one document in one database operation."""
    if len(chunks) != len(embeddings):
        raise ValueError("Each chunk must have exactly one embedding.")

    if _uses_mongodb():
        collection = _get_mongodb_collection()
        collection.insert_many(
            [
                {
                    "source": document_name,
                    "document_name": document_name,
                    "chunk_text": chunk,
                    "embedding": embedding,
                }
                for chunk, embedding in zip(chunks, embeddings)
            ]
        )
        return

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                f"""
                INSERT INTO {POSTGRES_TABLE}
                    (source, document_name, chunk_text, embedding)
                VALUES (%s, %s, %s, %s::vector)
                """,
                [
                    (document_name, document_name, chunk, str(embedding))
                    for chunk, embedding in zip(chunks, embeddings)
                ],
            )


def save_chunk(document_name: str, chunk_text: str, embedding: list[float]) -> None:
    """Save one text chunk; kept for compatibility with older callers."""
    save_chunks(document_name, [chunk_text], [embedding])


def similarity_search(
    query_embedding: list[float], top_k: int = 5
) -> list[dict]:
    """Return the most similar chunks from the selected vector store."""
    if _uses_mongodb():
        collection = _get_mongodb_collection()
        pipeline = [
            {
                "$vectorSearch": {
                    "index": MONGODB_INDEX_NAME,
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": max(top_k * 10, 50),
                    "limit": top_k,
                }
            },
            {
                "$project": {
                    "document_name": 1,
                    "chunk_text": 1,
                    "similarity": {"$meta": "vectorSearchScore"},
                }
            },
        ]
        return [
            {
                "id": str(row["_id"]),
                "document_name": row.get("document_name", ""),
                "chunk_text": row.get("chunk_text", ""),
                "similarity": float(row.get("similarity", 0)),
            }
            for row in collection.aggregate(pipeline)
        ]

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, document_name, chunk_text,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM {POSTGRES_TABLE}
                WHERE embedding IS NOT NULL AND chunk_text IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (str(query_embedding), str(query_embedding), top_k),
            )
            rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "document_name": row[1],
            "chunk_text": row[2],
            "similarity": float(row[3]),
        }
        for row in rows
    ]
