from __future__ import annotations

from pathlib import Path

from pix.coding_demo import (
    load_coding_dashboard_snapshot,
    scripted_demo_messages,
    scripted_demo_provider,
    write_coding_dashboard_snapshot,
)


def test_scripted_demo_provider_replays_fix_loop() -> None:
    provider = scripted_demo_provider()
    assert provider.name == "scripted"
    assert len(scripted_demo_messages()) == 7
    assert provider.responses


def test_snapshot_persistence_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "snapshot.json"
    snapshot = {
        "schema_version": 1,
        "mode": "deterministic-scripted",
        "outcome": {"status": "success"},
    }

    write_coding_dashboard_snapshot(snapshot, target)

    assert load_coding_dashboard_snapshot(target) == snapshot
    assert load_coding_dashboard_snapshot(tmp_path / "missing.json") is None
