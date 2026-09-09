"""OpenAI embedding provider."""

from __future__ import annotations

from typing import Any

import httpx

from pix.embedding.base import EmbeddingProvider
from pix.errors import ProviderError


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai-embeddings"

    def __init__(
        self,
        api_key: str,
        *,
        api_base: str = "https://api.openai.com/v1",
        model: str = "text-embedding-3-small",
        timeout: float = 30.0,
    ) -> None:
        self.model = model
        self._client = httpx.Client(
            base_url=api_base.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = self._client.post(
                "/embeddings",
                json={"model": self.model, "input": texts},
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Embedding request failed: {exc}") from exc
        if response.is_error:
            try:
                detail: Any = response.json()
                message = detail.get("error", {}).get("message", detail)
            except ValueError:
                message = response.text
            raise ProviderError(f"Embedding API error {response.status_code}: {message}")
        data = response.json().get("data", [])
        vectors: list[list[float]] = []
        for item in data:
            values = item.get("embedding")
            if isinstance(values, list) and all(isinstance(value, (int, float)) for value in values):
                vectors.append([float(value) for value in values])
        if len(vectors) != len(texts):
            raise ProviderError("Embedding API returned an unexpected vector count")
        return vectors
