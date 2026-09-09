"""Standard library logging helpers for CLI and API processes."""

from __future__ import annotations

import logging
import sys

LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def setup_logging(level: str = "INFO", *, use_rich: bool = True) -> None:
    """Configure root logging with a human-friendly handler.

    Rich output is only enabled when stderr supports a terminal, so tests and
    automation keep plain, machine-readable logs.
    """

    root = logging.getLogger()
    root.setLevel(LEVELS.get(level.upper(), logging.INFO))

    for existing_handler in list(root.handlers):
        root.removeHandler(existing_handler)

    handler: logging.Handler
    if use_rich and sys.stderr.isatty():
        try:
            from rich.logging import RichHandler

            handler = RichHandler(rich_tracebacks=True, show_path=False)
        except ImportError:  # pragma: no cover - rich is always installed
            handler = logging.StreamHandler()
    else:
        handler = logging.StreamHandler()

    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s"))
    root.addHandler(handler)
