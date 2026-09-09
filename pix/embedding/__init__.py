"""Embedding provider abstraction."""

from pix.embedding.base import EmbeddingProvider
from pix.embedding.local import HashingEmbeddingProvider, MockEmbeddingProvider
from pix.embedding.openai import OpenAIEmbeddingProvider
from pix.errors import ProviderError


def create_embedding_provider(
    name: str = "local",
    *,
    api_key: str | None = None,
    api_base: str = "https://api.openai.com/v1",
    model: str = "text-embedding-3-small",
) -> EmbeddingProvider:
    """Create an embedding provider by name.

    The default ``local`` provider requires no network or API key and is meant
    for deterministic offline tests. ``openai`` requires an API key and is only
    used when an explicit embedding backend is configured.
    """

    provider_name = name.lower()
    if provider_name == "openai":
        if not api_key:
            raise ProviderError(
                "OPENAI_API_KEY is required for the openai embedding provider. "
                "Set it in the environment or use PIX_EMBEDDING_PROVIDER=local."
            )
        return OpenAIEmbeddingProvider(api_key, api_base=api_base, model=model)
    if provider_name == "local":
        return HashingEmbeddingProvider()
    if provider_name == "mock":
        return MockEmbeddingProvider()
    raise ProviderError(f"Unknown embedding provider: {name}")


__all__ = [
    "EmbeddingProvider",
    "HashingEmbeddingProvider",
    "MockEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "create_embedding_provider",
]
