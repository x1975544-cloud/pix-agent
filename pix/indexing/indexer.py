"""Scan, chunk, embed and search a repository."""

from __future__ import annotations

from pathlib import Path

from pix.embedding.base import EmbeddingProvider
from pix.errors import ProviderError
from pix.indexing.chroma_store import ChromaVectorStore
from pix.indexing.documents import IndexedChunk, RepositoryDocument, SearchResult

SUPPORTED_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".md",
    ".json",
    ".yaml",
    ".yml",
}

IGNORED_DIRECTORIES = {
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
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".pix",
}

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
}


class RepositoryIndexer:
    """Build a semantic search index for source documents."""

    def __init__(
        self,
        embedding: EmbeddingProvider,
        vector_store_path: str | Path = ".pix/vectors",
        collection_name: str = "pix_repository",
        *,
        chunk_size: int = 1_200,
        chunk_overlap: int = 120,
    ) -> None:
        self.embedding = embedding
        self.vector_store = ChromaVectorStore(vector_store_path, collection_name)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def index_repository(self, root: str | Path) -> list[IndexedChunk]:
        root_path = Path(root).resolve()
        if not root_path.is_dir():
            raise FileNotFoundError(f"Repository not found: {root_path}")
        documents = self._scan(root_path)
        chunks = [chunk for document in documents for chunk in self.chunk_document(document, root_path)]
        if not chunks:
            return []
        vectors = self.embedding.embed([chunk.content for chunk in chunks])
        self.vector_store.add(chunks, vectors)
        return chunks

    def search_repository(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not query.strip():
            raise ProviderError("Search query cannot be empty")
        vector = self.embedding.embed([query])[0]
        return self.vector_store.search(vector, limit=limit)

    def _scan(self, root: Path) -> list[RepositoryDocument]:
        documents: list[RepositoryDocument] = []
        for path in root.rglob("*"):
            if any(part in IGNORED_DIRECTORIES for part in path.relative_to(root).parts):
                continue
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            try:
                size = path.stat().st_size
                if size > 500_000:
                    continue
                data = path.read_bytes()
                if b"\x00" in data[:8192]:
                    continue
                content = data.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            relative = str(path.relative_to(root)).replace("\\", "/")
            language = LANGUAGE_BY_SUFFIX[path.suffix.lower()]
            documents.append(
                RepositoryDocument(
                    path=relative,
                    language=language,
                    content=content,
                    metadata={"bytes": path.stat().st_size},
                )
            )
        return documents

    def chunk_document(self, document: RepositoryDocument, root: Path) -> list[IndexedChunk]:
        lines = document.content.splitlines()
        chunks: list[IndexedChunk] = []
        if not lines:
            return chunks
        start = 0
        while start < len(lines):
            end = min(len(lines), start + max(1, self.chunk_size // 40))
            content = "\n".join(lines[start:end])
            chunks.append(
                IndexedChunk(
                    id=f"{document.path}:{start + 1}:{end}",
                    document_path=document.path,
                    language=document.language,
                    content=content,
                    start_line=start + 1,
                    end_line=end,
                    metadata=document.metadata,
                )
            )
            if end >= len(lines):
                break
            start = max(start + 1, end - max(0, self.chunk_overlap // 40))
        return chunks


__all__ = ["RepositoryIndexer"]
