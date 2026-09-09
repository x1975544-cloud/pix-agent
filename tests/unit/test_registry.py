from __future__ import annotations

import pytest
from pix.security import Workspace
from pix.tools.base import ToolNotFoundError
from pix.tools.filesystem import ListDirectoryTool
from pix.tools.registry import ToolRegistry


def test_registry_roundtrip(tmp_path):
    registry = ToolRegistry([ListDirectoryTool(Workspace(tmp_path))])
    assert registry.has("list_directory")
    assert registry.get("list_directory").name == "list_directory"
    assert len(registry.schemas()) == 1
    assert registry.schemas()[0]["type"] == "function"
    assert registry.unregister("list_directory") is not None
    assert not registry.has("list_directory")


def test_registry_missing_tool():
    registry = ToolRegistry([])
    with pytest.raises(ToolNotFoundError):
        registry.get("missing")


def test_registry_rejects_duplicate(tmp_path):
    registry = ToolRegistry([])
    registry.register(ListDirectoryTool(Workspace(tmp_path)))
    with pytest.raises(ValueError):
        registry.register(ListDirectoryTool(Workspace(tmp_path)))
