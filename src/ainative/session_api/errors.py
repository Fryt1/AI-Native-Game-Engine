"""The one error an Agent-supplied Workflow can raise before it runs."""

from __future__ import annotations


class WorkflowError(RuntimeError):
    """The Agent supplied a Workflow that cannot be opened for validation."""
