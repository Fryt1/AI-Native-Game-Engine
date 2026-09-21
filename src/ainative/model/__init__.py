"""Pure data structures. Nothing here talks to a host, a Tool, or a file.

A Workflow **is** a tree: ``WorkflowTree`` holds one ``WorkflowNode`` root, and a
node is either a STAGE (leaf, holds calls and its frozen checklists) or a WORKFLOW
(composite, holds children and reads their verdicts). A phase is not a separate
type -- a phase is a WORKFLOW node used for grouping.
"""

from .artifacts import ArtifactRef
from .checklists import (
    AcceptanceCheck,
    ChecklistSummary,
    CheckOperator,
    CheckResult,
    CheckStatus,
    ExecutionChecklistItem,
    ExecutionItemResult,
    StageKind,
)
from .results import ExecutionResult, StageResult, TaskResult, TaskStatus
from .task import TaskContract
from .tools import CallTarget, ToolCall, call_digest
from .tree import (
    ROOT_PATH,
    COMPLETE_STATUSES,
    SATISFIED_STATUSES,
    UNRESOLVED_STATUSES,
    GateResult,
    NodeCheck,
    NodeKind,
    ReusePlan,
    StageBody,
    WorkflowNode,
    WorkflowStatus,
    WorkflowTree,
    depth,
    join_path,
    leaves,
    node_fingerprint,
    normalise_path,
    parent_path,
    paths,
    plan_reuse,
    resolve,
    resolve_relative,
    tree_fingerprints,
    walk,
)

__all__ = [
    "AcceptanceCheck",
    "ArtifactRef",
    "CallTarget",
    "CheckOperator",
    "CheckResult",
    "CheckStatus",
    "ChecklistSummary",
    "COMPLETE_STATUSES",
    "ExecutionChecklistItem",
    "ExecutionItemResult",
    "ExecutionResult",
    "GateResult",
    "NodeCheck",
    "NodeKind",
    "ROOT_PATH",
    "ReusePlan",
    "SATISFIED_STATUSES",
    "StageBody",
    "StageKind",
    "StageResult",
    "TaskContract",
    "TaskResult",
    "TaskStatus",
    "ToolCall",
    "UNRESOLVED_STATUSES",
    "WorkflowNode",
    "WorkflowStatus",
    "WorkflowTree",
    "call_digest",
    "depth",
    "join_path",
    "leaves",
    "node_fingerprint",
    "normalise_path",
    "parent_path",
    "paths",
    "plan_reuse",
    "resolve",
    "resolve_relative",
    "tree_fingerprints",
    "walk",
]
