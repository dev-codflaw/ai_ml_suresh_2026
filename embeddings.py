"""Create embeddings for document chunks and user questions."""

from functools import lru_cache

from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    """Load one embedding model and reuse it."""
    return SentenceTransformer(MODEL_NAME)


def get_embedding(text: str) -> list[float]:
    """Convert text into a vector using the same model every time."""
    return get_embeddings([text])[0]


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Convert multiple texts in one model call."""
    if not texts:
        return []
    vectors = get_model().encode(texts, convert_to_numpy=True)
    return vectors.tolist()
