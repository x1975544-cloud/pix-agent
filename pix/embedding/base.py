"""Interface for vectorizing memory text."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Turn text into dense numeric vectors."""

    name: str = "base"

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of strings into equal-length vectors."""
