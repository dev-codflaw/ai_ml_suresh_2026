"""Small PostgreSQL + pgvector data-access functions."""

from db import get_connection


def create_table() -> None:
    """Create or update the chunks table without deleting existing data."""
    sql = """
        CREATE EXTENSION IF NOT EXISTS vector;

        CREATE TABLE IF NOT EXISTS document_chunks (
            id SERIAL PRIMARY KEY,
            source TEXT NOT NULL,
            document_name TEXT NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding vector(384) NOT NULL
        );

        ALTER TABLE document_chunks
            ADD COLUMN IF NOT EXISTS source TEXT;

        ALTER TABLE document_chunks
            ADD COLUMN IF NOT EXISTS document_name TEXT;

        ALTER TABLE document_chunks
            ADD COLUMN IF NOT EXISTS chunk_text TEXT;

        ALTER TABLE document_chunks
            ADD COLUMN IF NOT EXISTS embedding vector(384);
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)


def save_chunk(document_name: str, chunk_text: str, embedding: list[float]) -> None:
    """Save one text chunk and its embedding."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO document_chunks
                    (source, document_name, chunk_text, embedding)
                VALUES (%s, %s, %s, %s::vector)
                """,
                (document_name, document_name, chunk_text, str(embedding)),
            )


def similarity_search(
    query_embedding: list[float], top_k: int = 5
) -> list[dict]:
    """Return the most similar chunks using cosine distance."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, document_name, chunk_text,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM document_chunks
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
