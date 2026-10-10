"""The document-ingestion steps: PDF -> text -> chunks -> vectors."""

from pathlib import Path

import fitz
from langchain_text_splitters import RecursiveCharacterTextSplitter

from embeddings import get_embedding
from vector_store import create_table, save_chunk


def load_pdf(file_path: str | Path) -> fitz.Document:
    """Open a PDF file."""
    return fitz.open(str(file_path))


def extract_text(file_path: str | Path) -> str:
    """Extract plain text from every page in a PDF."""
    with load_pdf(file_path) as pdf:
        return "\n".join(page.get_text("text") for page in pdf)


def create_chunks(text: str) -> list[str]:
    """Split text into small, overlapping chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
    )
    return splitter.split_text(text)


def ingest_document(file_path: str | Path) -> dict:
    """Extract, chunk, embed, and save one PDF."""
    document_name = Path(file_path).name
    text = extract_text(file_path).strip()

    if not text:
        raise ValueError("The PDF does not contain readable text.")

    chunks = create_chunks(text)
    create_table()

    first_embedding = get_embedding(chunks[0])
    save_chunk(document_name, chunks[0], first_embedding)

    for chunk in chunks[1:]:
        save_chunk(document_name, chunk, get_embedding(chunk))

    return {
        "document_name": document_name,
        "text": text,
        "chunks": chunks,
        "embedding_dimension": len(first_embedding),
        "example_embedding": first_embedding,
    }
