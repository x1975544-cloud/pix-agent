"""Code search across the workspace using ripgrep with a Python fallback."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pix.errors import ToolError
from pix.security import Workspace, is_binary
from pix.tools.base import Tool

IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
    ".idea",
    ".vscode",
}


class SearchCodeTool(Tool):
    """Return file, line and snippet matches for a text query."""

    name = "search_code"
    description = "Search repository source files for text or a simple pattern. Uses ripgrep when available."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Literal text or regular expression to find.",
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search, relative to the workspace root.",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, workspace: Workspace, *, max_results: int = 50, max_file_bytes: int = 200_000) -> None:
        self.workspace = workspace
        self.max_results = max_results
        self.max_file_bytes = max_file_bytes

    def run(self, arguments: dict[str, Any]) -> Any:
        query = str(arguments["query"])
        if not query:
            raise ToolError("search query cannot be empty")
        raw_path = arguments.get("path", ".")
        try:
            root = self.workspace.resolve(raw_path)
        except Exception as exc:
            raise ToolError(str(exc)) from exc
        if not root.exists():
            raise ToolError(f"Search path does not exist: {raw_path}")
        rg = shutil.which("rg")
        if rg:
            try:
                hits = self._search_with_rg(rg, query, root)
            except Exception:
                hits = self._search_python(query, root)
        else:
            hits = self._search_python(query, root)
        for hit in hits:
            hit["file"] = self._relative_to_workspace(hit["file"])
        return {"query": query, "count": len(hits), "hits": hits[: self.max_results]}

    def _relative_to_workspace(self, path: str) -> str:
        try:
            return str(Path(path).resolve().relative_to(self.workspace.root))
        except ValueError:
            return path

    def _search_with_rg(self, binary: str, query: str, root: Path) -> list[dict[str, Any]]:
        ignored_args: list[str] = []
        for directory in sorted(IGNORED_DIRECTORIES):
            ignored_args.extend(["--glob", f"!**/{directory}/**", "--glob", f"!**/{directory}"])
        command = [
            binary,
            "--json",
            "--line-number",
            "--no-heading",
            "--max-count",
            str(self.max_results),
            *ignored_args,
            "--",
            query,
            str(root),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return self._parse_rg_output(completed.stdout)

    @classmethod
    def _parse_rg_output(cls, output: str) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for raw_line in output.splitlines():
            if not raw_line.strip():
                continue
            try:
                message = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if message.get("type") != "match":
                continue
            data = message.get("data", {})
            file_path = str(data.get("path", {}).get("text", ""))
            text = str(data.get("lines", {}).get("text", "")).rstrip("\n")
            line_number = int(data.get("line_number") or 0)
            if file_path and text is not None:
                hits.append({"file": file_path, "line": line_number, "snippet": text})
        return hits

    def _search_python(self, query: str, root: Path) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        target = root.resolve()
        if target.is_file():
            iterator: Iterator[Path] = iter([target])
        else:
            iterator = target.rglob("*")
        for path in iterator:
            if len(hits) >= self.max_results:
                break
            if path.is_dir():
                continue
            if path.name in {".git", ".hg", ".svn"}:
                continue
            try:
                relative = path.resolve().relative_to(self.workspace.root)
            except ValueError:
                continue
            parts = relative.parts
            if any(part in IGNORED_DIRECTORIES for part in parts):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size == 0 or size > self.max_file_bytes:
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if is_binary(data):
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                continue
            lines = text.splitlines()
            for index, line in enumerate(lines):
                if query in line:
                    start = max(0, index - 1)
                    end = min(len(lines), index + 2)
                    hits.append(
                        {
                            "file": str(relative),
                            "line": index + 1,
                            "snippet": "\n".join(lines[start:end]),
                        }
                    )
                    if len(hits) >= self.max_results:
                        break
        return hits


def default_search_tool(workspace: Workspace, max_results: int, max_file_bytes: int) -> Tool:
    return SearchCodeTool(workspace, max_results=max_results, max_file_bytes=max_file_bytes)
