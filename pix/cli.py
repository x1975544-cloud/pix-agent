"""Rich-powered PiX command line interface."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pix import __version__
from pix.agent.agent import Agent
from pix.config.settings import Settings
from pix.errors import PiXError
from pix.logging import setup_logging

app = typer.Typer(help="PiX Agent - autonomous software engineering runtime.", add_completion=False)
console = Console()

SUBCOMMANDS = {"run", "sessions", "trace", "tools", "skills", "benchmark", "serve"}


def _logo() -> Panel:
    return Panel(
        "[bold cyan]PiX Agent[/bold cyan]\nAutonomous Software Engineering Runtime",
        border_style="cyan",
        subtitle=f"v{__version__}",
    )


def _settings(verbose: bool = False) -> Settings:
    settings = Settings()
    if verbose:
        setup_logging("DEBUG")
    else:
        setup_logging(settings.log_level)
    return settings


@app.command()
def run(
    task: Annotated[str, typer.Argument(help="Natural-language software engineering task.")],
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", "-w", help="Repository workspace path."),
    ] = None,
    model: Annotated[str | None, typer.Option("--model", "-m", help="LLM model override.")] = None,
    max_iterations: Annotated[
        int | None,
        typer.Option("--max-iterations", help="Maximum agent loop iterations."),
    ] = None,
    auto_verify: Annotated[bool, typer.Option("--auto-verify/--no-auto-verify")] = True,
    auto_fix_attempts: Annotated[int, typer.Option("--auto-fix-attempts")] = 2,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Run a task against a workspace repository."""

    console.print(_logo())
    console.print(f"[bold]Task:[/bold] {task}")
    settings = _settings(verbose)
    agent = Agent(settings)
    try:
        result = agent.run(
            task,
            workspace=workspace,
            model=model,
            max_iterations=max_iterations,
            auto_verify=auto_verify,
            auto_fix_attempts=auto_fix_attempts,
        )
    except PiXError as exc:
        console.print(Panel(f"[red]Agent error[/red]\n{exc}", border_style="red"))
        raise typer.Exit(code=1) from exc
    finally:
        agent.close()

    status_style = "green" if result.status.value == "success" else "red"
    console.print(Panel(result.message, title="Final Answer", border_style=status_style))
    summary_lines = [
        f"Session: {result.state.session_id}",
        f"Status: {result.status.value}",
        f"Iterations: {result.state.iteration}",
        f"Tool observations: {len(result.state.observations)}",
        f"Workspace: {result.state.workspace}",
    ]
    if result.state.summary:
        summary_lines.append(f"Verification: {result.state.summary}")
    console.print("\n".join(summary_lines))
    if result.status.value != "success":
        raise typer.Exit(code=1)


@app.command()
def sessions(limit: Annotated[int, typer.Option("--limit")] = 20, verbose: bool = False) -> None:
    """List recorded agent sessions."""

    settings = _settings(verbose)
    agent = Agent(settings)
    try:
        records = agent.sessions(limit)
    finally:
        agent.close()
    table = Table(title="PiX Sessions")
    for column in ("ID", "Task", "Status", "Workspace", "Started"):
        table.add_column(column)
    for record in records:
        table.add_row(
            record.id,
            record.task[:60],
            record.status,
            record.workspace,
            record.started_at.isoformat(),
        )
    console.print(table)


@app.command()
def trace(session_id: Annotated[str, typer.Argument()], verbose: bool = False) -> None:
    """Print the trace timeline for a session."""

    settings = _settings(verbose)
    agent = Agent(settings)
    try:
        events = agent.trace(session_id)
    except PiXError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    finally:
        agent.close()
    console.print(f"[bold]Trace:[/bold] {session_id}")
    for index, event in enumerate(events, start=1):
        marker = "✓" if event.get("type") not in {"AGENT_ERROR", "TOOL_RESULT"} else "•"
        duration = f" [{event['duration_ms']:.1f}ms]" if event.get("duration_ms") is not None else ""
        summary = str(event.get("payload", {}))[:180]
        console.print(f"{index:>3} {marker} [cyan]{event['type']}[/cyan]{duration} {summary}")


@app.command()
def tools(verbose: bool = False) -> None:
    """List tools available to the agent runtime."""

    settings = _settings(verbose)
    from fastapi.testclient import TestClient

    from pix.api.app import create_app
    from pix.api.schemas import ToolInfo

    # Reuse the API catalog so CLI and HTTP expose exactly the same tools.
    application = create_app(settings)
    with TestClient(application) as client:
        items = [ToolInfo(**item) for item in client.get("/api/tools").json()]
    table = Table(title="PiX Tools")
    table.add_column("Name")
    table.add_column("Description")
    for item in items:
        table.add_row(item.name, item.description[:100])
    console.print(table)


@app.command()
def skills(verbose: bool = False) -> None:
    """List markdown skills available on disk."""

    settings = _settings(verbose)
    from pix.skills.loader import load_skills

    loaded = load_skills(settings.skills_dir)
    table = Table(title="PiX Skills")
    table.add_column("Name")
    table.add_column("Path")
    for skill in loaded:
        table.add_row(skill.name, str(skill.path))
    console.print(table)


@app.command()
def benchmark(
    task_dir: Annotated[
        Path,
        typer.Argument(help="Directory containing benchmark JSON task files."),
    ] = Path("benchmarks/tasks"),
    verbose: bool = False,
) -> None:
    """Run benchmark tasks with a live provider and write a report."""

    settings = _settings(verbose)
    from pix.evaluation.runner import BenchmarkRunner

    runner = BenchmarkRunner(settings)
    report = runner.run_directory(task_dir)
    console.print(report.summary_markdown())


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    verbose: bool = False,
) -> None:
    """Start the FastAPI server."""

    _settings(verbose)
    import uvicorn

    console.print(f"[cyan]PiX API[/cyan] listening on http://{host}:{port}")
    uvicorn.run("pix.api.app:app", host=host, port=port, reload=reload)


def main() -> None:
    """Console entry point that supports both `pix run ...` and bare `pix \"task\"`."""

    argv = sys.argv[1:]
    known = SUBCOMMANDS | {"--help", "-h", "--version"}
    if argv and argv[0] not in known:
        argv.insert(0, "run")
    sys.argv = [sys.argv[0], *argv]
    app()


if __name__ == "__main__":
    main()
