"""The document-ingestion steps: PDF -> text -> chunks -> vectors."""

from pathlib import Path
from typing import TypeAlias

import fitz

from embeddings import get_embeddings
from vector_store import create_table, save_chunks


PdfSource: TypeAlias = str | Path | bytes | bytearray | memoryview


def load_pdf(source: PdfSource) -> fitz.Document:
    """Open a PDF path or an in-memory PDF byte string."""
    if isinstance(source, (bytes, bytearray, memoryview)):
        return fitz.open(stream=bytes(source), filetype="pdf")
    return fitz.open(str(source))


def extract_text(source: PdfSource) -> str:
    """Extract plain text from every page in a PDF."""
    with load_pdf(source) as pdf:
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


def ingest_document(source: PdfSource, document_name: str | None = None) -> dict:
    """Extract, chunk, embed, and save one PDF from a path or bytes."""
    if document_name is None:
        if isinstance(source, (bytes, bytearray, memoryview)):
            document_name = "document.pdf"
        else:
            document_name = Path(source).name
    else:
        document_name = Path(document_name).name

    text = extract_text(source).strip()

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
