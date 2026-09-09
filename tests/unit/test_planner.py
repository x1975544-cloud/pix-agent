from __future__ import annotations

import json

from pix.agent.planner import Planner
from pix.providers.base import ChatMessage
from tests.conftest import ScriptedProvider


def test_planner_parses_plan():
    plan = {
        "title": "Add JWT login",
        "summary": "Add auth to the API.",
        "steps": [
            {"title": "Analyze repository", "description": "Read project files."},
            {"title": "Implement", "description": "Add JWT module and tests."},
        ],
    }
    provider = ScriptedProvider([ChatMessage.assistant(json.dumps(plan))])
    result = Planner(provider).plan("Add JWT login")
    assert result.title == "Add JWT login"
    assert len(result.steps) == 2


def test_planner_rejects_invalid_json():
    provider = ScriptedProvider([ChatMessage.assistant("not json")])
    try:
        Planner(provider).plan("Anything")
    except Exception as exc:
        assert "invalid JSON" in str(exc)
    else:
        raise AssertionError("Expected invalid JSON error")
