"""Deterministic node acceptance, task aggregation, and the confirmation gate.

A STAGE node is judged by :class:`StageAcceptanceEvaluator`; the whole tree,
including the composite roll-up, by :func:`evaluate_tree`. The operator
vocabulary is defined once, in ``evaluator``, and used by both.
"""

from .aggregation import aggregate_task_status, next_action_for, outstanding_nodes
from .confirmation import confirmation_gate
from .evaluator import (
    CHECK_STATUS_TO_TASK_STATUS,
    StageAcceptance,
    StageAcceptanceEvaluator,
    apply_check,
    compare,
    read_field,
    summarise_checklist,
)
from .tree_evaluator import (
    NodeResult,
    blocking_paths,
    evaluate_tree,
    summarise_tree,
)

__all__ = [
    "CHECK_STATUS_TO_TASK_STATUS",
    "NodeResult",
    "StageAcceptance",
    "StageAcceptanceEvaluator",
    "aggregate_task_status",
    "apply_check",
    "blocking_paths",
    "compare",
    "confirmation_gate",
    "evaluate_tree",
    "next_action_for",
    "outstanding_nodes",
    "read_field",
    "summarise_checklist",
    "summarise_tree",
]
