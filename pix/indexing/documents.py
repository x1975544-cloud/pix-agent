"""Models shared by the repository indexer and its persistent snapshot."""

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
    """A bounded chunk of a source document with stable metadata."""

    id: str
    document_path: str
    language: str
    content: str
    start_line: int
    end_line: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RepositoryIndexReport:
    """Summary of one incremental indexing pass."""

    index_path: str
    total_files: int
    total_chunks: int
    added_files: int
    updated_files: int
    unchanged_files: int
    removed_files: int
    changed_chunks: int


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One repository chunk returned by semantic search."""

    chunk_id: str
    path: str
    content: str
    score: float
    language: str = "unknown"
    start_line: int = 1
    end_line: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def document_path(self) -> str:
        return self.path

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "path": self.path,
            "language": self.language,
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "score": self.score,
            "metadata": self.metadata,
        }
