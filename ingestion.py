"""The document-ingestion steps: PDF -> text -> chunks -> vectors."""

from pathlib import Path

import fitz
from langchain_text_splitters import RecursiveCharacterTextSplitter

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
