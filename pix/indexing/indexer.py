"""Incremental, dependency-free repository indexing."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pix.embedding.base import EmbeddingProvider
from pix.indexing.documents import IndexedChunk, RepositoryIndexReport, SearchResult
from pix.vectorstore.base import VectorSearchResult, VectorStore

SUPPORTED_SUFFIXES = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "jsx",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".mts": "typescript",
    ".cts": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".sql": "sql",
    ".css": "css",
    ".scss": "scss",
    ".html": "html",
    ".vue": "vue",
    ".svelte": "svelte",
    ".proto": "protobuf",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".md": "markdown",
}

IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        ".next",
        "out",
        ".cache",
        ".turbo",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        ".idea",
        ".vscode",
        ".pix",
        "coverage",
        "htmlcov",
    }
)

IGNORED_FILE_NAMES = frozenset(
    {
        "cargo.lock",
        "go.sum",
        "npm-shrinkwrap.json",
        "package-lock.json",
        "pipfile.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "uv.lock",
        "yarn.lock",
    }
)


@dataclass(frozen=True, slots=True)
class _ScannedDocument:
    relative_path: str
    language: str
    content: str
    digest: str
    size_bytes: int
    mtime_ns: int


@dataclass(frozen=True, slots=True)
class _UpdateStats:
    added_files: int
    updated_files: int
    unchanged_files: int
    removed_files: int
    changed_chunks: int


def _chunk_to_dict(chunk: IndexedChunk) -> dict[str, Any]:
    return {
        "id": chunk.id,
        "document_path": chunk.document_path,
        "language": chunk.language,
        "content": chunk.content,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "metadata": dict(chunk.metadata),
    }


def _chunks_from_files(files: dict[str, dict[str, Any]]) -> list[IndexedChunk]:
    chunks: list[IndexedChunk] = []
    for record in files.values():
        for raw_chunk in record.get("chunks", []):
            chunks.append(
                IndexedChunk(
                    id=str(raw_chunk["id"]),
                    document_path=str(raw_chunk["document_path"]),
                    language=str(raw_chunk["language"]),
                    content=str(raw_chunk["content"]),
                    start_line=int(raw_chunk["start_line"]),
                    end_line=int(raw_chunk["end_line"]),
                    metadata=dict(raw_chunk.get("metadata") or {}),
                )
            )
    return chunks


def _empty_snapshot(root: Path, index_path: Path) -> dict[str, Any]:
    return {
        "version": 1,
        "root": str(root),
        "updated_at": datetime.now(UTC).isoformat(),
        "index_path": str(index_path),
        "files": {},
    }


def _load_snapshot(index_path: Path) -> dict[str, Any]:
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"files": {}}
    files = data.get("files")
    if not isinstance(files, dict):
        return {"files": {}}
    return {"version": data.get("version", 1), "root": data.get("root"), "files": files}


def _save_snapshot(index_path: Path, snapshot: dict[str, Any]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=index_path.parent,
            prefix=f".{index_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(snapshot, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if temp_path is None:
            raise RuntimeError("Could not create temporary index file")
        temp_path.replace(index_path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def _metadata_int(metadata: dict[str, Any], key: str) -> int:
    try:
        return int(metadata[key])
    except (KeyError, TypeError, ValueError):
        return 1


class RepositoryIndexer:
    """Scan source files and persist deterministic chunks as JSON.

    The index is content-addressed by file digest. Unchanged files are loaded
    from the existing snapshot, changed files are re-chunked, and removed files
    are dropped during the next pass.
    """

    def __init__(
        self,
        index_path: str | Path | None = None,
        *,
        chunk_size: int = 1_000,
        chunk_overlap: int = 100,
        max_file_size: int = 500_000,
        embedding: EmbeddingProvider | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        self._index_path = Path(index_path) if index_path else None
        self.chunk_size = chunk_size
        self.chunk_overlap = min(chunk_overlap, max(0, chunk_size - 1))
        self.max_file_size = max_file_size
        self.embedding = embedding
        self.vector_store = vector_store

    def index_repository(self, root: str | Path) -> list[IndexedChunk]:
        """Index or incrementally update a workspace and return all chunks."""

        previous_ids = self._previous_chunk_ids(root)
        snapshot, _stats = self._update(root)
        chunks = _chunks_from_files(snapshot["files"])
        self._sync_semantic_index(chunks, previous_ids)
        return chunks

    def update_repository(self, root: str | Path) -> RepositoryIndexReport:
        """Run one incremental pass and return what changed."""

        previous_ids = self._previous_chunk_ids(root)
        snapshot, stats = self._update(root)
        chunks = _chunks_from_files(snapshot["files"])
        self._sync_semantic_index(chunks, previous_ids)
        return self._build_report(root, snapshot, stats)

    def search_repository(
        self,
        query: str,
        *,
        top_k: int = 10,
        limit: int | None = None,
    ) -> list[SearchResult]:
        """Run top-K semantic search against the configured vector store."""

        if self.embedding is None or self.vector_store is None:
            raise ValueError("Semantic search requires embedding and vector_store")
        if not query.strip():
            raise ValueError("Search query cannot be empty")
        vector = self.embedding.embed([query])[0]
        matches = self.vector_store.query(vector, limit=limit if limit is not None else top_k)
        return [self._search_result(match) for match in matches]

    def _previous_chunk_ids(self, root: str | Path) -> set[str]:
        if self.embedding is None or self.vector_store is None:
            return set()
        index_path = self._resolve_index_path(Path(root).expanduser().resolve())
        previous = _load_snapshot(index_path)
        return {
            str(raw_chunk["id"])
            for record in previous.get("files", {}).values()
            for raw_chunk in record.get("chunks", [])
        }

    def _sync_semantic_index(
        self,
        chunks: list[IndexedChunk],
        previous_ids: set[str],
    ) -> None:
        if self.embedding is None or self.vector_store is None:
            return
        current_ids = {chunk.id for chunk in chunks}
        stale_ids = previous_ids - current_ids
        if stale_ids:
            self.vector_store.delete(list(stale_ids))
        if chunks:
            vectors = self.embedding.embed([chunk.content for chunk in chunks])
            self.vector_store.upsert(
                [chunk.id for chunk in chunks],
                vectors,
                [self._chunk_metadata(chunk) for chunk in chunks],
            )

    @staticmethod
    def _chunk_metadata(chunk: IndexedChunk) -> dict[str, Any]:
        metadata = dict(chunk.metadata)
        metadata.update(
            {
                "path": chunk.document_path,
                "chunk_id": chunk.id,
                "content": chunk.content,
                "language": chunk.language,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
            }
        )
        return metadata

    @staticmethod
    def _search_result(match: VectorSearchResult) -> SearchResult:
        metadata = dict(match.metadata)
        return SearchResult(
            chunk_id=match.chunk_id,
            path=match.path,
            content=match.content,
            score=match.score,
            language=str(metadata.get("language", "unknown")),
            start_line=_metadata_int(metadata, "start_line"),
            end_line=_metadata_int(metadata, "end_line"),
            metadata=metadata,
        )

    def _update(self, root: str | Path) -> tuple[dict[str, Any], _UpdateStats]:
        root_path = Path(root).expanduser().resolve()
        if not root_path.is_dir():
            raise FileNotFoundError(f"Repository not found: {root_path}")
        index_path = self._resolve_index_path(root_path)
        previous = _load_snapshot(index_path)
        previous_files = previous.get("files")
        if not isinstance(previous_files, dict):
            previous_files = {}

        scanned = self._scan(root_path, index_path)
        indexed_at = datetime.now(UTC).isoformat()
        files: dict[str, dict[str, Any]] = {}
        added = 0
        updated = 0
        unchanged = 0
        changed_chunks = 0
        current_paths: set[str] = set()

        for document in scanned:
            current_paths.add(document.relative_path)
            old_record = previous_files.get(document.relative_path)
            if old_record is not None and old_record.get("digest") == document.digest:
                files[document.relative_path] = old_record
                unchanged += 1
                continue
            chunks = self._chunk_document(document)
            files[document.relative_path] = {
                "path": document.relative_path,
                "language": document.language,
                "digest": document.digest,
                "size_bytes": document.size_bytes,
                "mtime_ns": document.mtime_ns,
                "indexed_at": indexed_at,
                "chunks": [_chunk_to_dict(chunk) for chunk in chunks],
            }
            if old_record is None:
                added += 1
            else:
                updated += 1
            changed_chunks += len(chunks)

        removed = 0
        for path in previous_files:
            if path not in current_paths:
                removed += 1

        snapshot = _empty_snapshot(root_path, index_path)
        snapshot["files"] = files
        if added or updated or removed or not index_path.exists():
            _save_snapshot(index_path, snapshot)
        stats = _UpdateStats(
            added_files=added,
            updated_files=updated,
            unchanged_files=unchanged,
            removed_files=removed,
            changed_chunks=changed_chunks,
        )
        return snapshot, stats

    def _build_report(
        self,
        root: str | Path,
        snapshot: dict[str, Any],
        stats: _UpdateStats,
    ) -> RepositoryIndexReport:
        files = snapshot["files"]
        total_chunks = sum(len(record.get("chunks", [])) for record in files.values())
        return RepositoryIndexReport(
            index_path=str(self._resolve_index_path(Path(root).expanduser().resolve())),
            total_files=len(files),
            total_chunks=total_chunks,
            added_files=stats.added_files,
            updated_files=stats.updated_files,
            unchanged_files=stats.unchanged_files,
            removed_files=stats.removed_files,
            changed_chunks=stats.changed_chunks,
        )

    def _resolve_index_path(self, root: Path) -> Path:
        if self._index_path is None:
            return root / ".pix" / "repository-index.json"
        path = self._index_path
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    def _scan(self, root: Path, index_path: Path) -> list[_ScannedDocument]:
        documents: list[_ScannedDocument] = []
        resolved_index_path = index_path.resolve()
        for current_root, dirs, files in os.walk(root):
            current = Path(current_root)
            dirs[:] = sorted(
                (name for name in dirs if name.lower() not in IGNORED_DIRECTORIES),
                key=str.lower,
            )
            for name in sorted(files, key=str.lower):
                path = current / name
                if path.is_symlink() or not path.is_file():
                    continue
                relative = path.relative_to(root)
                if relative.name.lower() in IGNORED_FILE_NAMES:
                    continue
                language = SUPPORTED_SUFFIXES.get(path.suffix.lower())
                if language is None:
                    continue
                try:
                    stat = path.stat()
                    data = path.read_bytes()
                except OSError:
                    continue
                if stat.st_size <= 0 or stat.st_size > self.max_file_size:
                    continue
                if b"\x00" in data[:8192]:
                    continue
                try:
                    content = data.decode("utf-8-sig")
                except UnicodeDecodeError:
                    continue
                if path.resolve() == resolved_index_path:
                    continue
                documents.append(
                    _ScannedDocument(
                        relative_path=relative.as_posix(),
                        language=language,
                        content=content,
                        digest=hashlib.sha256(data).hexdigest(),
                        size_bytes=stat.st_size,
                        mtime_ns=stat.st_mtime_ns,
                    )
                )
        return documents

    def _chunk_document(self, document: _ScannedDocument) -> list[IndexedChunk]:
        content = document.content
        if not content.strip():
            return []
        chunks: list[IndexedChunk] = []
        used_ids: set[str] = set()
        position = 0
        step = max(1, self.chunk_size - self.chunk_overlap)
        metadata = {
            "bytes": document.size_bytes,
            "mtime_ns": document.mtime_ns,
            "digest": document.digest,
        }
        while position < len(content):
            end = min(len(content), position + self.chunk_size)
            segment = content[position:end]
            start_line = content.count("\n", 0, position) + 1
            segment_lines = segment.splitlines()
            end_line = start_line + len(segment_lines) - 1 if segment_lines else start_line
            chunk_id = f"{document.relative_path}:{start_line}:{end_line}"
            if chunk_id in used_ids:
                chunk_id = f"{chunk_id}:{position + 1}"
            used_ids.add(chunk_id)
            chunks.append(
                IndexedChunk(
                    id=chunk_id,
                    document_path=document.relative_path,
                    language=document.language,
                    content=segment,
                    start_line=start_line,
                    end_line=end_line,
                    metadata=dict(metadata),
                )
            )
            position += step
        return chunks


__all__ = ["RepositoryIndexer"]
