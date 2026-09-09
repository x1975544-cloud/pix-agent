"""Provider factory for environment-driven model backends."""

from __future__ import annotations

import logging
from typing import Any

from pix.config.settings import Settings
from pix.errors import ProviderError
from pix.providers.base import LLMProvider
from pix.providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)


def create_provider(settings: Settings, provider_name: str | None = None, **overrides: Any) -> LLMProvider:
    """Create an LLM provider from settings.

    ``provider_name`` currently accepts ``openai``. Anthropic, Gemini and
    local providers are intentionally left as registry extension points; a
    missing provider raises :class:`ProviderError` instead of silently
    returning a stub.
    """

    name = (provider_name or "openai").lower()
    if name == "openai":
        api_key = settings.api_key.get_secret_value() if settings.api_key else None
        return OpenAIProvider(
            api_key,
            api_base=str(overrides.get("api_base", settings.api_base)),
            model=str(overrides.get("model", settings.model)),
            timeout=float(overrides.get("request_timeout", settings.request_timeout)),
        )
    if name in {"anthropic", "gemini", "ollama", "local"}:
        raise ProviderError(
            f"Provider '{name}' is reserved for a future release. The architecture supports it via "
            "pix.providers.base.LLMProvider, but no implementation is shipped yet."
        )
    raise ProviderError(f"Unknown provider: {name}")
