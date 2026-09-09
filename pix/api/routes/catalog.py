"""Tool and skill catalog routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from pix.api.schemas import SkillInfo, ToolInfo
from pix.security import Workspace
from pix.skills.loader import load_skills
from pix.tools.filesystem import default_filesystem_tools
from pix.tools.git import default_git_tools
from pix.tools.registry import ToolRegistry
from pix.tools.search import default_search_tool
from pix.tools.shell import default_shell_tool

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/tools", response_model=list[ToolInfo])
def list_tools(request: Request) -> list[ToolInfo]:
    settings = request.app.state.settings
    workspace = Workspace(request.app.state.agent.executor.settings.workspace)
    registry = ToolRegistry(
        [
            *default_filesystem_tools(workspace, settings.max_file_bytes),
            default_shell_tool(workspace, settings.shell_timeout),
            default_search_tool(workspace, settings.max_search_results, settings.max_file_bytes),
            *default_git_tools(str(workspace.root)),
        ]
    )
    return [ToolInfo(name=tool.name, description=tool.description) for tool in registry.list()]


@router.get("/skills", response_model=list[SkillInfo])
def list_skills(request: Request) -> list[SkillInfo]:
    skills = load_skills(request.app.state.settings.skills_dir)
    return [SkillInfo(name=skill.name, path=str(skill.path)) for skill in skills]
