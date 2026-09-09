"""Document and chunk models used by the repository indexer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RepositoryDocument:
    """One UTF-8 source document discovered under the workspace."""

    path: str
    language: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def root_path(self) -> Path:
        return Path(self.path)


@dataclass(slots=True)
class IndexedChunk:
    """A bounded chunk of a document, ready for embedding."""

    id: str
    document_path: str
    language: str
    content: str
    start_line: int
    end_line: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SearchResult:
    """One semantic retrieval hit."""

    chunk_id: str
    document_path: str
    language: str
    content: str
    start_line: int
    end_line: int
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "path": self.document_path,
            "language": self.language,
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "score": self.score,
            "metadata": self.metadata,
        }
