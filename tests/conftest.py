"""Shared test fixtures."""

from __future__ import annotations

import pytest
from pix.providers.scripted import ScriptedProvider

__all__ = ["ScriptedProvider"]


@pytest.fixture
def scripted_provider() -> ScriptedProvider:
    return ScriptedProvider([])
