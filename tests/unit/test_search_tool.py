from __future__ import annotations

from pix.security import Workspace
from pix.tools.search import SearchCodeTool


def test_search_finds_matches(tmp_path):
    (tmp_path / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("answer is unknown\n", encoding="utf-8")
    workspace = Workspace(tmp_path)
    result = SearchCodeTool(workspace, max_results=10).execute({"query": "return 42"})
    assert result.success
    assert result.output["hits"][0]["file"] == "app.py"


def test_search_skips_ignored_directories(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("TOKEN_MARKER\n", encoding="utf-8")
    (tmp_path / "src.js").write_text("TOKEN_MARKER\n", encoding="utf-8")
    workspace = Workspace(tmp_path)
    result = SearchCodeTool(workspace, max_results=20).execute({"query": "TOKEN_MARKER"})
    files = [hit["file"] for hit in result.output["hits"]]
    assert files == ["src.js"]
