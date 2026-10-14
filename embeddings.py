"""Create local vectors without downloading an embedding model.

The vector database expects 384-value vectors.  A stable hashing vectorizer
keeps that interface without an external embedding package or model download.
Documents and questions use the same algorithm, so they remain searchable in
the selected vector store.
"""

import hashlib
import math
import re


EMBEDDING_DIMENSIONS = 384
_TOKEN_PATTERN = re.compile(r"[\w]+", re.UNICODE)


def _token_features(text: str) -> list[str]:
    """Return word and short character-ngram features for a text."""
    tokens = [token.lower() for token in _TOKEN_PATTERN.findall(text)]
    features = list(tokens)

    for token in tokens:
        padded = f"^{token}$"
        features.extend(
            padded[index : index + 3]
            for index in range(max(0, len(padded) - 2))
        )
    return features


def _feature_index(feature: str) -> tuple[int, float]:
    """Map a feature to an index and a repeatable positive/negative sign."""
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    number = int.from_bytes(digest, byteorder="big")
    index = number % EMBEDDING_DIMENSIONS
    sign = 1.0 if number & 1 else -1.0
    return index, sign


def get_embedding(text: str) -> list[float]:
    """Convert one text into a normalized, deterministic vector."""
    return get_embeddings([text])[0]


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Convert texts into normalized vectors without network or model access."""
    vectors: list[list[float]] = []

    for text in texts:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for feature in _token_features(text):
            index, sign = _feature_index(feature)
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        vectors.append(vector)

    return vectors
