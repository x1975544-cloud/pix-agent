"""Real OpenAI end-to-end smoke test.

This script intentionally calls the configured OpenAI-compatible API. It fails
with a non-zero exit code when the key is missing, invalid, rate limited or the
agent does not perform the expected repository tool calls.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pix.agent.agent import Agent
from pix.config.settings import Settings
from pix.errors import PiXError
from pix.providers.base import ChatMessage
from pix.providers.factory import create_provider


def _tool_names(agent: Agent, session_id: str) -> set[str]:
    names: set[str] = set()
    for event in agent.trace(session_id):
        if event.get("type") != "TOOL_CALL":
            continue
        name = event.get("payload", {}).get("name")
        if name:
            names.add(str(name))
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real OpenAI E2E smoke test.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("examples/demo-project"),
        help="Repository used by the agent tasks.",
    )
    parser.add_argument(
        "--skip-agent",
        action="store_true",
        help="Only validate provider connectivity and protocol encoding.",
    )
    args = parser.parse_args()

    settings = Settings()
    if not settings.api_key:
        print("FAIL: OPENAI_API_KEY is not set.")
        return 2

    provider = create_provider(settings)
    print(f"Provider: {provider.name}")
    print(f"Model: {settings.model}")
    try:
        result = provider.generate(
            [ChatMessage.user("Reply with exactly: OK")],
            model=settings.model,
        )
    except PiXError as exc:
        print(f"FAIL: provider request failed: {exc}")
        return 1
    finally:
        provider.close()

    answer = result.message.content.strip()
    print(f"Direct response: {answer[:120]}")
    if "ok" not in answer.lower():
        print("FAIL: direct provider response did not contain 'OK'.")
        return 1

    if args.skip_agent:
        print("PASS: provider connectivity and response parsing verified.")
        return 0

    workspace = args.workspace.expanduser().resolve()
    if not workspace.is_dir():
        print(f"FAIL: workspace not found: {workspace}")
        return 1

    tasks = [
        ("Analyze the demo repository and tell me what framework it uses.", {"list_directory"}),
        ("Read the README of the demo repository and summarize it.", {"read_file"}),
    ]

    agent = Agent(settings)
    try:
        for task, required_tools in tasks:
            print(f"\nTask: {task}")
            try:
                run = agent.run(task, workspace=workspace, auto_verify=False)
            except PiXError as exc:
                print(f"FAIL: agent task failed: {exc}")
                return 1
            if run.status.value != "success":
                print(f"FAIL: agent status={run.status.value}, message={run.message}")
                return 1
            tools = _tool_names(agent, run.state.session_id)
            missing = required_tools - tools
            if missing:
                print(f"FAIL: expected real tool calls {sorted(missing)}; observed {sorted(tools)}")
                return 1
            print(f"PASS: {run.message[:240]}")
            print(f"Observed tools: {sorted(tools)}")
    finally:
        agent.close()

    print("\nPASS: OpenAI real E2E completed with repository analysis and tool calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
