"""Deserialize an Agent-authored Workflow from JSON.

The Agent writes the Workflow; this module only reads it back into the framework's
model objects so the Workflow can be validated and its checklists evaluated. It makes no
decisions: it does not choose calls, order stages, or add missing items.

A malformed Workflow raises ``WorkflowDeserializationError`` naming the exact JSON path,
so the Agent can repair the document rather than guess.
"""

from __future__ import annotations

from typing import Any

from ainative.model.artifacts import ArtifactKind, ArtifactRef
from ainative.model.checklists import (
    AcceptanceCheck,
    CheckOperator,
    CheckResult,
    CheckStatus,
    ExecutionChecklistItem,
    ExecutionItemResult,
)
from ainative.model.results import ExecutionResult, TaskStatus
from ainative.model.task import TaskContract, TaskRoute
from ainative.model.tools import CallTarget, ToolCall
from ainative.model.workflow import (
    StageKind,
    StageRequest,
    Workflow,
    WorkflowStatus,
    WorkflowStep,
)


class WorkflowDeserializationError(ValueError):
    """The Agent-supplied Workflow document cannot be read."""


def _require(document: Any, key: str, path: str) -> Any:
    if not isinstance(document, dict):
        raise WorkflowDeserializationError(f"{path}: expected an object")
    if key not in document:
        raise WorkflowDeserializationError(f"{path}: missing required field '{key}'")
    return document[key]


def _str_tuple(value: Any, path: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise WorkflowDeserializationError(f"{path}: expected a list of strings")
    return tuple(value)


def _enum(enum_type: Any, value: Any, path: str) -> Any:
    if not isinstance(value, str):
        raise WorkflowDeserializationError(f"{path}: expected a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in enum_type)
        raise WorkflowDeserializationError(
            f"{path}: '{value}' is not one of: {allowed}"
        ) from exc


def tool_call_from_dict(document: Any, path: str) -> ToolCall:
    """Read one Tool call.

    @param document: the JSON object for one call.
    @param path: the JSON path, used in error messages.
    @returns the call contract.
    """

    arguments = document.get("arguments", {})
    if not isinstance(arguments, dict):
        raise WorkflowDeserializationError(f"{path}.arguments: expected an object")
    target = _require(document, "target", path)
    if not isinstance(target, dict):
        raise WorkflowDeserializationError(f"{path}.target: expected an object")
    return ToolCall(
        call_id=str(_require(document, "call_id", path)),
        target=CallTarget(
            owner=str(_require(target, "owner", f"{path}.target")),
            name=str(_require(target, "name", f"{path}.target")),
        ),
        arguments=arguments,
        depends_on=_str_tuple(document.get("depends_on"), f"{path}.depends_on"),
    )


def execution_item_from_dict(document: Any, path: str) -> ExecutionChecklistItem:
    """Read one execution checklist item."""

    return ExecutionChecklistItem(
        item_id=str(_require(document, "item_id", path)),
        description=str(document.get("description", "")),
        required=bool(document.get("required", True)),
        call_ids=_str_tuple(document.get("call_ids"), f"{path}.call_ids"),
        evidence_required=bool(document.get("evidence_required", True)),
        metadata=dict(document.get("metadata", {})),
    )


def acceptance_check_from_dict(document: Any, path: str) -> AcceptanceCheck:
    """Read one acceptance check."""

    return AcceptanceCheck(
        check_id=str(_require(document, "check_id", path)),
        description=str(document.get("description", "")),
        required=bool(document.get("required", True)),
        call_ids=_str_tuple(document.get("call_ids"), f"{path}.call_ids"),
        source_call_id=document.get("source_call_id"),
        actual_path=_str_tuple(document.get("actual_path"), f"{path}.actual_path"),
        operator=_enum(CheckOperator, document.get("operator", CheckOperator.MANUAL.value), f"{path}.operator"),
        expected=document.get("expected"),
        tolerance=document.get("tolerance"),
        evidence_required=bool(document.get("evidence_required", True)),
        metadata=dict(document.get("metadata", {})),
    )


def stage_from_dict(document: Any, path: str) -> StageRequest:
    """Read one Stage, including both frozen checklists."""

    calls = _require(document, "calls", path) if "calls" in document else []
    if not isinstance(calls, list):
        raise WorkflowDeserializationError(f"{path}.calls: expected a list")
    items = document.get("execution_checklist", [])
    checks = document.get("acceptance_checklist", [])
    if not isinstance(items, list):
        raise WorkflowDeserializationError(f"{path}.execution_checklist: expected a list")
    if not isinstance(checks, list):
        raise WorkflowDeserializationError(f"{path}.acceptance_checklist: expected a list")
    return StageRequest(
        stage_id=str(_require(document, "stage_id", path)),
        purpose=str(document.get("purpose", "")),
        operation=str(document.get("operation", "")),
        calls=tuple(
            tool_call_from_dict(call, f"{path}.calls[{index}]")
            for index, call in enumerate(calls)
        ),
        stage_kind=_enum(StageKind, document.get("stage_kind", StageKind.CHANGE.value), f"{path}.stage_kind"),
        execution_checklist=tuple(
            execution_item_from_dict(item, f"{path}.execution_checklist[{index}]")
            for index, item in enumerate(items)
        ),
        acceptance_checklist=tuple(
            acceptance_check_from_dict(check, f"{path}.acceptance_checklist[{index}]")
            for index, check in enumerate(checks)
        ),
        depends_on=_str_tuple(document.get("depends_on"), f"{path}.depends_on"),
        required=bool(document.get("required", True)),
        recovery=document.get("recovery"),
    )


def step_from_dict(document: Any, path: str) -> WorkflowStep:
    """Read one Step."""

    stages = _require(document, "stages", path)
    if not isinstance(stages, list):
        raise WorkflowDeserializationError(f"{path}.stages: expected a list")
    return WorkflowStep(
        step_id=str(_require(document, "step_id", path)),
        purpose=str(document.get("purpose", "")),
        stages=tuple(
            stage_from_dict(stage, f"{path}.stages[{index}]")
            for index, stage in enumerate(stages)
        ),
        depends_on=_str_tuple(document.get("depends_on"), f"{path}.depends_on"),
        optional=bool(document.get("optional", False)),
    )


def artifact_from_dict(document: Any, path: str) -> ArtifactRef:
    """Read one artifact reference."""

    return ArtifactRef(
        artifact_id=str(_require(document, "artifact_id", path)),
        kind=_enum(ArtifactKind, document.get("kind", ArtifactKind.UNKNOWN.value), f"{path}.kind"),
        uri=str(_require(document, "uri", path)),
        provider_id=document.get("provider_id"),
        media_type=document.get("media_type"),
        metadata=dict(document.get("metadata", {})),
    )


def task_from_dict(raw: Any, path: str = "task") -> TaskContract:
    """Read a TaskContract document.

    @param raw: the JSON task object.
    @param path: the JSON path, used in error messages.
    @returns the task contract.
    @throws WorkflowDeserializationError when the document is malformed.
    """

    if not isinstance(raw, dict):
        raise WorkflowDeserializationError(f"{path}: expected an object")
    return TaskContract(
        task_id=str(raw.get("task_id", "cli-task")),
        objective=str(raw.get("objective", "")),
        route=_enum(TaskRoute, raw.get("route", TaskRoute.HOST_OPERATION.value), f"{path}.route"),
        asset_type=str(raw.get("asset_type", "unknown")),
        direction=str(raw.get("direction", "none")),
        preserve_relations=frozenset(raw.get("preserve_relations", [])),
        guidance=raw.get("guidance"),
        source_context=dict(raw.get("source_context", {})),
        target_context=dict(raw.get("target_context", {})),
        confirmation_required=bool(raw.get("confirmation_required", False)),
        metadata=dict(raw.get("metadata", {})),
    )


def execution_result_from_dict(document: Any, path: str) -> ExecutionResult:
    """Read one executed call result the Agent submits as evidence.

    @param document: the JSON object for one call result.
    @param path: the JSON path, used in error messages.
    @returns the execution result contract.
    """

    if not isinstance(document, dict):
        raise WorkflowDeserializationError(f"{path}: expected an object")
    outputs = document.get("outputs", {})
    if not isinstance(outputs, dict):
        raise WorkflowDeserializationError(f"{path}.outputs: expected an object")
    artifacts = document.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise WorkflowDeserializationError(f"{path}.artifacts: expected a list")
    preserved = document.get("preserved_relations", [])
    lost = document.get("lost_relations", [])
    if not isinstance(preserved, list) or not isinstance(lost, list):
        raise WorkflowDeserializationError(f"{path}: preserved_relations and lost_relations must be lists")
    target_document = document.get("target")
    if target_document is not None and not isinstance(target_document, dict):
        raise WorkflowDeserializationError(f"{path}.target: expected an object")
    target = (
        CallTarget(
            owner=str(_require(target_document, "owner", f"{path}.target")),
            name=str(_require(target_document, "name", f"{path}.target")),
        )
        if target_document is not None
        else None
    )
    return ExecutionResult(
        call_id=str(_require(document, "call_id", path)),
        status=_enum(TaskStatus, _require(document, "status", path), f"{path}.status"),
        target=target,
        outputs=outputs,
        artifacts=tuple(
            artifact_from_dict(artifact, f"{path}.artifacts[{index}]")
            for index, artifact in enumerate(artifacts)
        ),
        warnings=_str_tuple(document.get("warnings"), f"{path}.warnings"),
        errors=_str_tuple(document.get("errors"), f"{path}.errors"),
        resume_pointer=document.get("resume_pointer"),
        preserved_relations=frozenset(preserved),
        lost_relations=frozenset(lost),
    )


def execution_item_result_from_dict(document: Any, path: str) -> ExecutionItemResult:
    """Read one execution checklist item result the Agent submits."""

    if not isinstance(document, dict):
        raise WorkflowDeserializationError(f"{path}: expected an object")
    return ExecutionItemResult(
        item_id=str(_require(document, "item_id", path)),
        status=_enum(CheckStatus, _require(document, "status", path), f"{path}.status"),
        call_ids=_str_tuple(document.get("call_ids"), f"{path}.call_ids"),
        evidence_refs=_str_tuple(document.get("evidence_refs"), f"{path}.evidence_refs"),
        reason=str(document.get("reason", "")),
    )


def check_result_from_dict(document: Any, path: str) -> CheckResult:
    """Read one acceptance check result the Agent submits."""

    if not isinstance(document, dict):
        raise WorkflowDeserializationError(f"{path}: expected an object")
    return CheckResult(
        check_id=str(_require(document, "check_id", path)),
        status=_enum(CheckStatus, _require(document, "status", path), f"{path}.status"),
        actual=document.get("actual"),
        expected=document.get("expected"),
        evidence_refs=_str_tuple(document.get("evidence_refs"), f"{path}.evidence_refs"),
        reason=str(document.get("reason", "")),
    )


def workflow_from_dict(document: Any) -> Workflow:
    """Read an Agent-authored Workflow document.

    @param document: the Workflow JSON, either the Workflow itself or wrapped in
        ``{"workflow": {...}}``.
    @returns the Workflow ready for validation and evaluation.
    @throws WorkflowDeserializationError when a required field is missing or malformed.
    """

    if not isinstance(document, dict):
        raise WorkflowDeserializationError("plan: expected an object")
    workflow_document = document.get("workflow", document)
    path = "plan.workflow" if "workflow" in document else "plan"
    if not isinstance(workflow_document, dict):
        raise WorkflowDeserializationError(f"{path}: expected an object")

    steps = _require(workflow_document, "steps", path)
    if not isinstance(steps, list):
        raise WorkflowDeserializationError(f"{path}.steps: expected a list")

    workflow_id = workflow_document.get("workflow_id", "")
    workflow = Workflow(
        guidance=str(workflow_document.get("guidance", "")),
        route=_enum(TaskRoute, _require(workflow_document, "route", path), f"{path}.route"),
        steps=tuple(
            step_from_dict(step, f"{path}.steps[{index}]")
            for index, step in enumerate(steps)
        ),
        workflow_id=str(workflow_id),
        revision=int(workflow_document.get("revision", 1)),
        status=_enum(
            WorkflowStatus,
            workflow_document.get("status", WorkflowStatus.DRAFT.value),
            f"{path}.status",
        ),
        supersedes_workflow_id=workflow_document.get("supersedes_workflow_id"),
        replacement_reason=workflow_document.get("replacement_reason"),
        recovery_pointer=workflow_document.get("recovery_pointer"),
        warnings=_str_tuple(workflow_document.get("warnings"), f"{path}.warnings"),
    )
    return (workflow)
