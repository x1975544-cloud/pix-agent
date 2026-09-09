from __future__ import annotations

from pix.security import Workspace
from pix.tools.filesystem import ListDirectoryTool, ReadFileTool, WriteFileTool


def test_list_read_write_roundtrip(tmp_path):
    workspace = Workspace(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8", newline="")
    listing = ListDirectoryTool(workspace).execute({"path": "src"})
    assert listing.success
    assert listing.output["entries"][0]["name"] == "app.py"

    content = ReadFileTool(workspace, 200_000).execute({"path": "src/app.py"})
    assert content.output["content"] == "print('ok')\n"

    written = WriteFileTool(workspace, 200_000).execute({"path": "src/main.py", "content": "def main():\n    pass\n"})
    assert written.success
    assert (tmp_path / "src" / "main.py").exists()


def test_filesystem_rejects_traversal(tmp_path):
    workspace = Workspace(tmp_path)
    read = ReadFileTool(workspace, 100_000).execute({"path": "../secret.txt"})
    assert not read.success
    assert "workspace" in (read.error or "").lower()


def test_read_rejects_binary(tmp_path):
    workspace = Workspace(tmp_path)
    (tmp_path / "image.bin").write_bytes(b"\x00\x01\x02\xff")
    result = ReadFileTool(workspace, 100_000).execute({"path": "image.bin"})
    assert not result.success
    assert "binary" in (result.error or "").lower()


def test_write_rejects_oversized_content(tmp_path):
    workspace = Workspace(tmp_path)
    result = WriteFileTool(workspace, 20).execute({"path": "large.txt", "content": "x" * 100})
    assert not result.success


def test_read_missing_file(tmp_path):
    workspace = Workspace(tmp_path)
    result = ReadFileTool(workspace, 100_000).execute({})
    assert not result.success
    assert "path" in (result.error or "")
