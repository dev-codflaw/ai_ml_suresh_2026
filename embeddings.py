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
    vector = get_model().encode(text, convert_to_numpy=True)
    return vector.tolist()
