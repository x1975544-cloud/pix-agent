"""Deterministic local embedding provider for offline vector-store integration.

This is intentionally not a neural semantic encoder. It produces stable,
length-preserving hashed vectors so Chroma can be exercised without silently
calling an unknown third-party API. It is useful for integration tests and
small local repositories, not as a replacement for a trained embedding model.
"""

from __future__ import annotations

import hashlib
import re

from pix.embedding.base import EmbeddingProvider

_TOKEN = re.compile(r"[A-Za-z0-9_]+")


class HashingEmbeddingProvider(EmbeddingProvider):
    """Hash word n-grams into a deterministic 256-dimensional vector."""

    name = "local-hashing"

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = _TOKEN.findall(text.lower())
        grams = tokens + [f"{left}_{right}" for left, right in zip(tokens, tokens[1:], strict=False)]
        for gram in grams:
            digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = sum(value * value for value in vector) ** 0.5
        if norm:
            vector = [value / norm for value in vector]
        return vector


class MockEmbeddingProvider(HashingEmbeddingProvider):
    """Named mock embedding provider for deterministic offline tests."""

    name = "mock"


__all__ = ["HashingEmbeddingProvider", "MockEmbeddingProvider"]
