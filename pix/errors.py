"""Unified error hierarchy for the PiX runtime.

Every layer exposes domain errors that extend :class:`PiXError`. The API layer
converts these into HTTP responses and the CLI renders them with Rich, while
the tracer only records redacted, safe error metadata.
"""

from __future__ import annotations


class PiXError(Exception):
    """Base class for all expected PiX runtime errors."""


class ProviderError(PiXError):
    """Raised when an LLM provider cannot complete a request."""


class ToolError(PiXError):
    """Raised when a tool execution fails."""


class ToolTimeoutError(ToolError):
    """Raised when a tool exceeds its configured timeout."""


class ContextError(PiXError):
    """Raised when the context manager cannot build a valid prompt."""


class MemoryError(PiXError):
    """Raised when persistent or semantic memory operations fail."""


class SecurityError(PiXError):
    """Raised when an operation violates a sandbox or safety policy."""


class VerificationError(PiXError):
    """Raised when project verification cannot run or fails."""


class AgentLoopError(PiXError):
    """Raised when the agent loop terminates in an invalid state."""


class SessionNotFoundError(PiXError):
    """Raised when a requested session does not exist."""
