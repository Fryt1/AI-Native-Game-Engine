"""Deterministic Stage acceptance, task aggregation, and the confirmation gate."""

from .aggregation import aggregate_task_status, next_action_for, outstanding_stages
from .confirmation import confirmation_gate
from .evaluator import StageAcceptance, StageAcceptanceEvaluator

__all__ = [
    "StageAcceptance",
    "StageAcceptanceEvaluator",
    "aggregate_task_status",
    "confirmation_gate",
    "next_action_for",
    "outstanding_stages",
]
