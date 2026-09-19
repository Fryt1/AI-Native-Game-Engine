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
    StageKind,
)
from ainative.model.results import ExecutionResult, TaskStatus
from ainative.model.task import TaskContract
from ainative.model.tools import CallTarget, ToolCall
from ainative.model.tree import (
    NodeCheck,
    NodeKind,
    StageBody,
    WorkflowNode,
    WorkflowStatus,
    WorkflowTree,
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


def _target(value: Any, path: str) -> CallTarget | None:
    """Read a call target.

    ``None`` is allowed: a guidance document names a call's role and leaves the
    target for the caller to bind after confirming the live server, so a document
    may legitimately carry no target yet.
    """

    if value is None:
        return None
    if not isinstance(value, dict):
        raise WorkflowDeserializationError(f"{path}: expected an object or null")
    owner = value.get("owner")
    name = value.get("name")
    if not owner or not name:
        raise WorkflowDeserializationError(
            f"{path}: a target needs both an owner and a name")
    return CallTarget(owner=str(owner), name=str(name))


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


def _optional_enum(enum_type: Any, value: Any, path: str) -> Any:
    """Read an enum that the document may leave out entirely.

    A missing value stays None so an incomplete document is reported by whichever
    check owns that requirement, rather than being rejected here for a field the
    schema -- not this reader -- decides is mandatory.
    """

    if value is None:
        return None
    return _enum(enum_type, value, path)


def tool_call_from_dict(document: Any, path: str, *, target_required: bool = True) -> ToolCall:
    """Read one Tool call.

    @param document: the JSON object for one call.
    @param path: the JSON path, used in error messages.
    @param target_required: when False, a call may carry ``"target": null``. A
        guidance document names a call's ROLE and leaves the target for the caller
        to bind after confirming the live server, so the tree form allows it while
        an executed Workflow does not.
    @returns the call contract.
    """

    arguments = document.get("arguments", {})
    if not isinstance(arguments, dict):
        raise WorkflowDeserializationError(f"{path}.arguments: expected an object")

    if target_required:
        target = _require(document, "target", path)
        if not isinstance(target, dict):
            raise WorkflowDeserializationError(f"{path}.target: expected an object")
        resolved = CallTarget(
            owner=str(_require(target, "owner", f"{path}.target")),
            name=str(_require(target, "name", f"{path}.target")),
        )
    else:
        resolved = _target(document.get("target"), f"{path}.target")

    return ToolCall(
        call_id=str(_require(document, "call_id", path)),
        target=resolved,
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


# --------------------------------------------------------------------------- #
# The Workflow
# --------------------------------------------------------------------------- #


def node_check_from_dict(document: Any, path: str) -> NodeCheck:
    """Read one node check, including its descendant reference.

    The schema declares ``source_node`` as a property of a node check, so that is
    where a document puts it. ``AcceptanceCheck`` carries it in ``metadata``
    instead, so this moves it across. Without the move a document written to the
    spec would resolve no descendant, and the failure would be silent -- the check
    would read a field that is not there rather than the node it named.
    """

    if not isinstance(document, dict):
        raise WorkflowDeserializationError(f"{path}: expected an object")

    metadata = dict(document.get("metadata") or {})
    source_node = document.get("source_node")
    if source_node:
        if not isinstance(source_node, str):
            raise WorkflowDeserializationError(f"{path}.source_node: expected a string")
        metadata["source_node"] = source_node

    payload = {key: value for key, value in document.items() if key != "source_node"}
    payload["metadata"] = metadata
    return NodeCheck(acceptance_check_from_dict(payload, path))


def _stage_body(document: Any, path: str) -> StageBody:
    """Read a STAGE node's body, reusing the flat readers for its lists."""

    if not isinstance(document, dict):
        raise WorkflowDeserializationError(f"{path}: expected an object")

    calls_document = _require(document, "calls", path)
    if not isinstance(calls_document, list):
        raise WorkflowDeserializationError(f"{path}.calls: expected a list")

    calls = tuple(
        tool_call_from_dict(call, f"{path}.calls[{index}]", target_required=False)
        for index, call in enumerate(calls_document)
        if isinstance(call, dict)
    )

    items_document = _require(document, "execution_checklist", path)
    if not isinstance(items_document, list):
        raise WorkflowDeserializationError(f"{path}.execution_checklist: expected a list")
    items = tuple(
        ExecutionChecklistItem(
            item_id=str(_require(item, "item_id", f"{path}.execution_checklist[{index}]")),
            description=str(item.get("description", "")),
            required=bool(item.get("required", True)),
            call_ids=_str_tuple(item.get("call_ids"), f"{path}.execution_checklist[{index}]"),
            metadata=dict(item.get("metadata") or {}),
        )
        for index, item in enumerate(items_document)
        if isinstance(item, dict)
    )

    checks_document = document.get("acceptance_checklist") or []
    if not isinstance(checks_document, list):
        raise WorkflowDeserializationError(f"{path}.acceptance_checklist: expected a list")
    checks = tuple(
        node_check_from_dict(check, f"{path}.acceptance_checklist[{index}]")
        for index, check in enumerate(checks_document)
    )

    return StageBody(
        calls=calls,
        execution_checklist=items,
        acceptance_checklist=checks,
        stage_kind=_enum(
            StageKind,
            document.get("stage_kind", StageKind.CHANGE.value),
            f"{path}.stage_kind",
        ),
    )


def node_from_dict(document: Any, path: str) -> WorkflowNode:
    """Read one node of a Workflow tree.

    The node is recursive: a STAGE carries a body, a WORKFLOW carries children.
    ``kind`` decides which, and an unknown kind is rejected rather than guessed.
    """

    if not isinstance(document, dict):
        raise WorkflowDeserializationError(f"{path}: expected an object")

    node_id = str(_require(document, "node_id", path))
    kind_document = _require(document, "kind", path)
    try:
        kind = NodeKind(kind_document)
    except ValueError as exc:
        raise WorkflowDeserializationError(
            f"{path}.kind: {kind_document!r} is not one of "
            f"{[member.value for member in NodeKind]}") from exc

    children_document = document.get("children") or []
    if not isinstance(children_document, list):
        raise WorkflowDeserializationError(f"{path}.children: expected a list")

    checks_document = document.get("acceptance_checklist") or []
    if not isinstance(checks_document, list):
        raise WorkflowDeserializationError(f"{path}.acceptance_checklist: expected a list")

    node = WorkflowNode(
        node_id=node_id,
        kind=kind,
        purpose=str(document.get("purpose", "")),
        required=bool(document.get("required", True)),
        depends_on=_str_tuple(document.get("depends_on"), f"{path}.depends_on"),
        stage=_stage_body(document["stage"], f"{path}.stage")
        if kind is NodeKind.STAGE and "stage" in document else None,
        children=tuple(
            node_from_dict(child, f"{path}.children[{index}]")
            for index, child in enumerate(children_document)
        ),
        acceptance_checklist=tuple(
            node_check_from_dict(check, f"{path}.acceptance_checklist[{index}]")
            for index, check in enumerate(checks_document)
        ),
        guidance=document.get("guidance"),
        recovery=document.get("recovery"),
        metadata=dict(document.get("metadata") or {}),
    )
    return node


def workflow_from_dict(document: Any) -> WorkflowTree:
    """Read an Agent-authored Workflow document.

    The Workflow's shape is a tree: a node is a STAGE (leaf) or a WORKFLOW
    (composite). There is no second, flat form to dispatch on.

    @param document: the Workflow JSON, either the Workflow itself or wrapped in
        ``{"workflow": {...}}``.
    @returns the tree, ready for structural validation and evaluation.
    @throws WorkflowDeserializationError when a required field is missing or malformed.
    """

    if not isinstance(document, dict):
        raise WorkflowDeserializationError("workflow: expected an object")
    body = document.get("workflow", document)
    path = "workflow.workflow" if "workflow" in document else "workflow"
    if not isinstance(body, dict):
        raise WorkflowDeserializationError(f"{path}: expected an object")

    return WorkflowTree(
        workflow_id=str(body.get("workflow_id", "")),
        root=node_from_dict(_require(body, "root", path), f"{path}.root"),
        guidance=body.get("guidance"),
        revision=int(body.get("revision", 1)),
        status=_enum(
            WorkflowStatus,
            body.get("status", WorkflowStatus.DRAFT.value),
            f"{path}.status",
        ),
        supersedes_workflow_id=body.get("supersedes_workflow_id"),
        recovery_pointer=body.get("recovery_pointer"),
        warnings=_str_tuple(body.get("warnings"), f"{path}.warnings"),
    )
