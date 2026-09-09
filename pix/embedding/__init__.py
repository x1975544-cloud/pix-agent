"""Embedding provider abstraction."""

from pix.embedding.base import EmbeddingProvider
from pix.embedding.openai import OpenAIEmbeddingProvider

__all__ = ["EmbeddingProvider", "OpenAIEmbeddingProvider"]
