from __future__ import annotations

import json

import pytest
from pix.indexing import RepositoryIndexer


def test_indexes_sources_and_excludes_generated_and_binary_files(tmp_path) -> None:
    root = tmp_path / "workspace"
    (root / "src").mkdir(parents=True)
    (root / "lib").mkdir()
    (root / ".git").mkdir()
    (root / "node_modules" / "pkg").mkdir(parents=True)
    (root / ".venv" / "bin").mkdir(parents=True)
    (root / ".pytest_cache").mkdir()
    (root / "__pycache__").mkdir()
    (root / "src" / "app.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n",
        encoding="utf-8",
        newline="",
    )
    (root / "lib" / "util.ts").write_text("export const answer = 42;\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (root / "node_modules" / "pkg" / "index.js").write_text("module.exports = {};\n", encoding="utf-8")
    (root / ".venv" / "bin" / "pip.py").write_text("print('ignored')\n", encoding="utf-8")
    (root / ".pytest_cache" / "nodeids").write_text("ignored\n", encoding="utf-8")
    (root / "__pycache__" / "compiled.py").write_text("ignored\n", encoding="utf-8")
    (root / "assets.bin.py").write_bytes(b"\x00\x01\x02binary")
    (root / "notes.txt").write_text("not source\n", encoding="utf-8")

    index_path = root / ".pix" / "repository-index.json"
    indexer = RepositoryIndexer(index_path=index_path)
    report = indexer.update_repository(root)

    assert report.added_files == 3
    assert report.total_files == 3
    assert report.unchanged_files == 0
    paths = [chunk.document_path for chunk in indexer.index_repository(root)]
    assert paths == ["README.md", "lib/util.ts", "src/app.py"]

    snapshot = json.loads(index_path.read_text(encoding="utf-8"))
    record = snapshot["files"]["src/app.py"]
    chunk = record["chunks"][0]
    assert chunk["document_path"] == "src/app.py"
    assert chunk["content"] == "from fastapi import FastAPI\napp = FastAPI()\n"
    assert chunk["metadata"]["digest"] == record["digest"]
    assert chunk["metadata"]["bytes"] == record["size_bytes"]


def test_incremental_update_skips_unchanged_files_and_removes_stale_paths(tmp_path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    app = root / "app.py"
    app.write_text("def answer():\n    return 42\n", encoding="utf-8")
    util = root / "util.ts"
    util.write_text("export const label = 'demo';\n", encoding="utf-8")
    index_path = root / ".pix" / "repository-index.json"
    indexer = RepositoryIndexer(index_path=index_path)

    first = indexer.update_repository(root)
    assert first.added_files == 2
    assert first.unchanged_files == 0
    first_snapshot = json.loads(index_path.read_text(encoding="utf-8"))

    app.write_text("def answer():\n    return 42\n", encoding="utf-8")
    second = indexer.update_repository(root)
    assert second.added_files == 0
    assert second.updated_files == 0
    assert second.unchanged_files == 2
    assert second.removed_files == 0
    second_snapshot = json.loads(index_path.read_text(encoding="utf-8"))
    assert second_snapshot["updated_at"] == first_snapshot["updated_at"]

    app.write_text("def answer():\n    return 43\n", encoding="utf-8")
    third = indexer.update_repository(root)
    assert third.updated_files == 1
    assert third.unchanged_files == 1
    assert third.total_files == 2

    app.unlink()
    fourth = indexer.update_repository(root)
    assert fourth.removed_files == 1
    assert fourth.total_files == 1
    assert [chunk.document_path for chunk in indexer.index_repository(root)] == ["util.ts"]


def test_chunking_is_bounded_and_deterministic(tmp_path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    source = root / "module.py"
    source.write_text("\n".join(f"line_{index} = {index}" for index in range(200)), encoding="utf-8")
    index_path_a = root / ".pix" / "index-a.json"
    index_path_b = root / ".pix" / "index-b.json"

    first = RepositoryIndexer(index_path=index_path_a, chunk_size=120, chunk_overlap=20).index_repository(root)
    second = RepositoryIndexer(index_path=index_path_b, chunk_size=120, chunk_overlap=20).index_repository(root)

    assert len(first) > 1
    assert all(len(chunk.content) <= 120 for chunk in first)
    assert [(chunk.id, chunk.content, chunk.start_line, chunk.end_line) for chunk in first] == [
        (chunk.id, chunk.content, chunk.start_line, chunk.end_line) for chunk in second
    ]
    assert len({chunk.id for chunk in first}) == len(first)


def test_missing_root_is_reported(tmp_path) -> None:
    indexer = RepositoryIndexer(index_path=tmp_path / "repository-index.json")
    with pytest.raises(FileNotFoundError):
        indexer.update_repository(tmp_path / "missing")
