"""Optional Agent-owned intent interpreter interface.

The project deliberately provides no default prompt interpreter. The Agent (or
an explicitly injected LLM adapter) owns the decision that turns user intent into
a :class:`TaskContract`; the runtime only validates the supplied contract and
plan.
"""

from __future__ import annotations

from typing import Protocol

from ainative.orchestration.contracts.task import TaskContract


class IntentInterpreter(Protocol):
    """Optional adapter implemented by the Agent or its LLM integration."""

    def interpret(self, prompt: str, task_id: str) -> TaskContract:
        """Return an Agent-authored TaskContract for a user prompt."""
        ...
