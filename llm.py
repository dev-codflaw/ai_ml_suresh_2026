"""Use Ollama only for the final answer."""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")


def generate_answer(question: str, context_chunks: list[dict]) -> str:
    """Ask Ollama to answer only from the retrieved chunks."""
    context = "\n\n".join(
        f"Chunk {index}:\n{chunk['chunk_text']}"
        for index, chunk in enumerate(context_chunks, start=1)
    )

    prompt = f"""
Answer the question using only the context below.
If the answer is not in the context, say: "I do not know based on the provided document."
Do not use outside knowledge.

Question:
{question}

Context:
{context}
""".strip()

    response = requests.post(
        f"{OLLAMA_URL.rstrip('/')}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
        },
        timeout=120,
    )

    if not response.ok:
        detail = response.text.strip() or response.reason
        raise RuntimeError(
            f"Ollama returned HTTP {response.status_code} from "
            f"{OLLAMA_URL.rstrip('/')}/api/generate: {detail}"
        )

    return response.json()["response"].strip()
