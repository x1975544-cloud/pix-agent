"""Runtime configuration.

All secrets are supplied through environment variables or ``.env``. No secret
value is embedded in source code. Settings follow the ``PIX_`` prefix except
for ``OPENAI_API_KEY``, which keeps the conventional OpenAI variable name.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from environment or ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        case_sensitive=False,
    )

    api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    api_token: SecretStr | None = Field(default=None, validation_alias="PIX_API_TOKEN")
    api_base: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("PIX_API_BASE", "OPENAI_BASE_URL"),
    )
    model: str = Field(default="gpt-4o-mini", validation_alias="PIX_MODEL")
    embedding_model: str = Field(default="text-embedding-3-small", validation_alias="PIX_EMBEDDING_MODEL")
    embedding_provider: str = Field(default="openai", validation_alias="PIX_EMBEDDING_PROVIDER")
    vector_store_path: Path = Field(default=Path(".pix/vectors"), validation_alias="PIX_VECTOR_STORE_PATH")
    chroma_collection: str = Field(default="pix_repository", validation_alias="PIX_CHROMA_COLLECTION")
    enable_repository_index: bool = Field(default=False, validation_alias="PIX_ENABLE_REPOSITORY_INDEX")

    workspace: Path = Field(default=Path("."), validation_alias="PIX_WORKSPACE")
    max_iterations: int = Field(default=30, ge=1, le=200, validation_alias="PIX_MAX_ITERATIONS")
    shell_timeout: float = Field(default=60.0, gt=0, validation_alias="PIX_SHELL_TIMEOUT")
    tool_timeout: float = Field(default=60.0, gt=0, validation_alias="PIX_TOOL_TIMEOUT")
    request_timeout: float = Field(default=120.0, gt=0, validation_alias="PIX_REQUEST_TIMEOUT")
    max_file_bytes: int = Field(default=200_000, ge=1_024, validation_alias="PIX_MAX_FILE_BYTES")
    max_search_results: int = Field(default=50, ge=1, le=500, validation_alias="PIX_MAX_SEARCH_RESULTS")
    context_limit_tokens: int = Field(default=64_000, ge=1_000, validation_alias="PIX_CONTEXT_LIMIT_TOKENS")

    database_url: str = Field(default="sqlite:///./pix-agent.db", validation_alias="PIX_DATABASE_URL")
    log_level: str = Field(default="INFO", validation_alias="PIX_LOG_LEVEL")
    auto_commit: bool = Field(default=False, validation_alias="PIX_AUTO_COMMIT")
    max_verification_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        validation_alias="PIX_MAX_VERIFICATION_RETRIES",
    )

    enable_mcp: bool = Field(default=False, validation_alias="PIX_ENABLE_MCP")
    mcp_servers: list[str] = Field(default_factory=list, validation_alias="PIX_MCP_SERVERS")
    skills_dir: Path = Field(default=Path("skills"), validation_alias="PIX_SKILLS_DIR")

    @property
    def secret_values(self) -> list[str]:
        """Return active secret values that must be redacted from traces."""

        values: list[str] = []
        if self.api_key:
            values.append(self.api_key.get_secret_value())
        if self.api_token:
            values.append(self.api_token.get_secret_value())
        return values

    def database_path(self) -> Path:
        """Resolve ``sqlite:///...`` URLs to a filesystem path."""

        if self.database_url.startswith("sqlite:///"):
            raw = self.database_url.removeprefix("sqlite:///")
        elif self.database_url.startswith("sqlite://"):
            raw = self.database_url.removeprefix("sqlite://")
        else:
            raise ValueError(f"Unsupported database URL: {self.database_url}")
        path = Path(raw)
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()


def build_settings(env_file: str | Path | None = ".env", **overrides: Any) -> Settings:
    """Build settings, optionally with an explicit env file or test overrides."""

    if env_file is None:
        return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]
    return Settings(_env_file=str(env_file), **overrides)  # type: ignore[call-arg]


@lru_cache
def cached_settings(env_file: str | Path | None = ".env") -> Settings:
    """Process-wide cached settings for CLI and API defaults."""

    return build_settings(env_file)
