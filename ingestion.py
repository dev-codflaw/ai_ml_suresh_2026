"""The document-ingestion steps: PDF -> text -> chunks -> vectors."""

from pathlib import Path

import fitz

from embeddings import get_embeddings
from vector_store import create_table, save_chunks


def load_pdf(file_path: str | Path) -> fitz.Document:
    """Open a PDF file."""
    return fitz.open(str(file_path))


def extract_text(file_path: str | Path) -> str:
    """Extract plain text from every page in a PDF."""
    with load_pdf(file_path) as pdf:
        return "\n".join(page.get_text("text") for page in pdf)


def create_chunks(text: str) -> list[str]:
    """Split text into small, overlapping chunks without external packages."""
    chunk_size = 800
    chunk_overlap = 100
    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            natural_break = max(
                text.rfind("\n\n", start, end),
                text.rfind("\n", start, end),
                text.rfind(" ", start, end),
            )
            if natural_break > start + chunk_size // 2:
                end = natural_break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        next_start = max(end - chunk_overlap, start + 1)
        if next_start >= len(text):
            break
        start = next_start

    return chunks


def ingest_document(file_path: str | Path) -> dict:
    """Extract, chunk, embed, and save one PDF."""
    document_name = Path(file_path).name
    text = extract_text(file_path).strip()

    if not text:
        raise ValueError("The PDF does not contain readable text.")

    chunks = create_chunks(text)
    if not chunks:
        raise ValueError("The PDF did not produce any text chunks.")

    embeddings = get_embeddings(chunks)
    create_table()
    save_chunks(document_name, chunks, embeddings)

    return {
        "document_name": document_name,
        "text": text,
        "chunks": chunks,
        "embedding_dimension": len(embeddings[0]),
        "example_embedding": embeddings[0],
    }
