"""Filesystem tools that are constrained to a workspace sandbox."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pix.errors import ToolError
from pix.security import Workspace, is_binary
from pix.tools.base import Tool


def _resolve(workspace: Workspace, path: str | Path) -> Path:
    value = path if path is not None else "."
    try:
        return workspace.resolve(value)
    except Exception as exc:
        raise ToolError(str(exc)) from exc


class ListDirectoryTool(Tool):
    """List entries in a directory with type, name and byte size."""

    name = "list_directory"
    description = "List files and subdirectories inside the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative or absolute path inside the workspace. Defaults to the workspace root.",
            }
        },
        "additionalProperties": False,
    }

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def run(self, arguments: dict[str, Any]) -> Any:
        path = _resolve(self.workspace, arguments.get("path", "."))
        if not path.exists():
            raise ToolError(f"Directory does not exist: {arguments.get('path', '.')}")
        if not path.is_dir():
            raise ToolError(f"Path is not a directory: {path}")
        entries: list[dict[str, Any]] = []
        for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            try:
                stat = child.stat()
            except OSError:
                continue
            entries.append(
                {
                    "name": child.name,
                    "type": "directory" if child.is_dir() else "file",
                    "size": stat.st_size,
                }
            )
        return {
            "path": str(path.relative_to(self.workspace.root)) or ".",
            "entries": entries,
            "count": len(entries),
        }


class ReadFileTool(Tool):
    """Read a UTF-8 text file inside the workspace."""

    name = "read_file"
    description = "Read a UTF-8 text file. Binary files and files above the size limit are rejected."
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Path of the file inside the workspace."}},
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(self, workspace: Workspace, max_file_bytes: int) -> None:
        self.workspace = workspace
        self.max_file_bytes = max_file_bytes

    def run(self, arguments: dict[str, Any]) -> Any:
        path = _resolve(self.workspace, arguments["path"])
        if not path.is_file():
            raise ToolError(f"File does not exist: {path}")
        size = path.stat().st_size
        if size > self.max_file_bytes:
            raise ToolError(f"File size {size} exceeds limit {self.max_file_bytes} bytes")
        data = path.read_bytes()
        if is_binary(data):
            raise ToolError(f"Refusing to read binary file: {path}")
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError(f"File is not valid UTF-8: {path}") from exc
        return {
            "path": str(path.relative_to(self.workspace.root)),
            "size": size,
            "content": content,
        }


class WriteFileTool(Tool):
    """Write or replace a UTF-8 text file inside the workspace."""

    name = "write_file"
    description = "Write UTF-8 text content to a file inside the workspace. Creates parent directories if needed."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Destination path inside the workspace."},
            "content": {"type": "string", "description": "Complete file content to write."},
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    def __init__(self, workspace: Workspace, max_file_bytes: int) -> None:
        self.workspace = workspace
        self.max_file_bytes = max_file_bytes

    def run(self, arguments: dict[str, Any]) -> Any:
        raw_content = arguments["content"]
        if not isinstance(raw_content, str):
            raise ToolError("write_file content must be a string")
        if len(raw_content.encode("utf-8")) > self.max_file_bytes:
            raise ToolError("File content exceeds the configured byte limit")
        path = _resolve(self.workspace, arguments["path"])
        if path.exists() and path.is_dir():
            raise ToolError(f"Cannot overwrite directory with a file: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw_content, encoding="utf-8")
        return {
            "path": str(path.relative_to(self.workspace.root)),
            "bytes": path.stat().st_size,
            "written": True,
        }


def default_filesystem_tools(workspace: Workspace, max_file_bytes: int) -> list[Tool]:
    """Build the sandboxed filesystem tool set."""

    return [
        ListDirectoryTool(workspace),
        ReadFileTool(workspace, max_file_bytes),
        WriteFileTool(workspace, max_file_bytes),
    ]


def format_json_result(value: dict[str, Any]) -> str:
    """Serialize a filesystem result for debugging and tests."""

    return json.dumps(value, ensure_ascii=False, default=str)
