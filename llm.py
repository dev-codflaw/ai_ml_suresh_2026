"""Generate the final answer with the configured LLM provider."""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_API_URL = os.getenv(
    "GEMINI_API_URL", "https://generativelanguage.googleapis.com/v1beta"
)


def _build_prompt(question: str, context_chunks: list[dict]) -> str:
    """Build the shared grounded-answer prompt for every provider."""
    context = "\n\n".join(
        f"Chunk {index}:\n{chunk['chunk_text']}"
        for index, chunk in enumerate(context_chunks, start=1)
    )

    return f"""
Answer the question using only the context below.
If the answer is not in the context, say: "I do not know based on the provided document."
Do not use outside knowledge.

Question:
{question}

Context:
{context}
""".strip()


def get_llm_label() -> str:
    """Return a short, user-facing name for the configured answer model."""
    if LLM_PROVIDER == "ollama":
        return f"Ollama ({OLLAMA_MODEL})"
    if LLM_PROVIDER in {"gemini", "google", "google-ai-studio"}:
        return f"Gemini ({GEMINI_MODEL})"
    return LLM_PROVIDER


def check_llm_connection() -> tuple[bool, str]:
    """Return whether the selected LLM is configured and reachable."""
    if LLM_PROVIDER == "ollama":
        if not OLLAMA_URL or not OLLAMA_MODEL:
            return False, "OLLAMA_URL or OLLAMA_MODEL is not configured."
        try:
            response = requests.get(
                f"{OLLAMA_URL.rstrip('/')}/api/tags", timeout=3
            )
            response.raise_for_status()
            models = {model.get("name") for model in response.json().get("models", [])}
            if OLLAMA_MODEL not in models:
                return False, f"Ollama is connected, but model '{OLLAMA_MODEL}' is not available."
            return True, f"Connected to Ollama ({OLLAMA_MODEL})."
        except Exception as error:
            return False, f"Ollama is not reachable: {error}"

    if LLM_PROVIDER in {"gemini", "google", "google-ai-studio"}:
        if not GEMINI_API_KEY:
            return False, "GEMINI_API_KEY is not configured."
        try:
            response = requests.get(
                f"{GEMINI_API_URL.rstrip('/')}/models/{GEMINI_MODEL}",
                headers={"x-goog-api-key": GEMINI_API_KEY},
                timeout=5,
            )
            response.raise_for_status()
            return True, f"Connected to Gemini ({GEMINI_MODEL})."
        except Exception as error:
            return False, f"Gemini is not available: {error}"

    return False, f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}."


def _generate_ollama(prompt: str) -> str:
    """Generate an answer through the local Ollama HTTP API."""
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


def _generate_gemini(prompt: str) -> str:
    """Generate an answer through the Google AI Studio Gemini API."""
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is required when LLM_PROVIDER=gemini. "
            "Add it to .env or the runtime environment."
        )

    response = requests.post(
        f"{GEMINI_API_URL.rstrip('/')}/models/{GEMINI_MODEL}:generateContent",
        headers={
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
        },
        timeout=120,
    )

    if not response.ok:
        detail = response.text.strip() or response.reason
        raise RuntimeError(
            f"Gemini returned HTTP {response.status_code} from "
            f"{GEMINI_MODEL}: {detail}"
        )

    payload = response.json()
    candidates = payload.get("candidates", [])
    if not candidates:
        feedback = payload.get("promptFeedback", {})
        raise RuntimeError(f"Gemini returned no answer: {feedback or payload}")

    answer = "".join(
        part.get("text", "")
        for part in candidates[0].get("content", {}).get("parts", [])
    ).strip()
    if not answer:
        raise RuntimeError(f"Gemini returned an empty answer: {payload}")

    return answer


def generate_answer(question: str, context_chunks: list[dict]) -> str:
    """Answer only from retrieved chunks using the selected provider."""
    prompt = _build_prompt(question, context_chunks)

    if LLM_PROVIDER == "ollama":
        return _generate_ollama(prompt)
    if LLM_PROVIDER in {"gemini", "google", "google-ai-studio"}:
        return _generate_gemini(prompt)

    raise RuntimeError(
        f"Unsupported LLM_PROVIDER={LLM_PROVIDER!r}. "
        "Use 'ollama' or 'gemini'."
    )
