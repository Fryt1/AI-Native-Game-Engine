"""Evaluate one STAGE node's frozen checklists from the evidence reported for it.

A STAGE is a leaf of the Workflow tree, addressed by its path. This module owns
what a *leaf* means: which execution items are satisfied, whether the acceptance
checks hold, and what verdict follows. Recursion -- a composite rolling up its
children, and a composite check reading a descendant -- belongs to
:mod:`ainative.acceptance.tree_evaluator`, which calls in here for every leaf so
the two layers never restate one another's rules.

Nothing here discovers or invokes a Tool. The Agent executes every call itself and
submits the result; this layer only judges what was submitted.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isclose
from typing import Any

from ainative.model.checklists import (
    AcceptanceCheck,
    ChecklistSummary,
    CheckOperator,
    CheckResult,
    CheckStatus,
    ExecutionChecklistItem,
    ExecutionItemResult,
)
from ainative.model.results import ExecutionResult, TaskStatus
from ainative.model.tree import WorkflowNode

#: How a node's checklist verdict maps onto the reported task vocabulary. A node
#: has a *verdict* (pass/fail/...); a task has a *status* (succeeded/failed/...).
#: The two are kept apart here and joined once, at the CLI boundary, so no layer
#: in between has to translate, and no translation can drift.
CHECK_STATUS_TO_TASK_STATUS = {
    CheckStatus.PASS: TaskStatus.SUCCEEDED,
    CheckStatus.WARN: TaskStatus.DEGRADED,
    CheckStatus.FAIL: TaskStatus.FAILED,
    CheckStatus.UNKNOWN: TaskStatus.BLOCKED,
    CheckStatus.NEEDS_HUMAN: TaskStatus.NEEDS_APPROVAL,
}


def compare(operator: CheckOperator, actual: Any, expected: Any,
            tolerance: float | None) -> bool:
    """Apply one operator. The single definition of what each operator means.

    Both layers use this: a leaf applying a check to a value read from a call, and
    a composite applying a check to a descendant's verdict. Two implementations of
    "what does equals mean" would be two chances to disagree.
    """

    if operator is CheckOperator.EXISTS:
        return actual is not None
    if operator is CheckOperator.TRUTHY:
        return bool(actual)
    if operator is CheckOperator.EQUALS:
        return actual == expected
    if operator is CheckOperator.SET_EQUALS:
        try:
            return set(actual) == set(expected)
        except TypeError:
            return False
    if operator is CheckOperator.COUNT_EQUALS:
        try:
            return len(actual) == int(expected)
        except (TypeError, ValueError):
            return False
    if operator is CheckOperator.WITHIN_TOLERANCE:
        return _within_tolerance(actual, expected, tolerance)
    return False


def _within_tolerance(actual: Any, expected: Any, tolerance: float | None) -> bool:
    selected_tolerance = 1e-6 if tolerance is None else float(tolerance)
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        return len(actual) == len(expected) and all(
            _within_tolerance(left, right, selected_tolerance)
            for left, right in zip(actual, expected)
        )
    try:
        return isclose(float(actual), float(expected), abs_tol=selected_tolerance, rel_tol=0.0)
    except (TypeError, ValueError):
        return False


def summarise_checklist(
    specs: tuple[Any, ...],
    results: tuple[Any, ...],
    result_id: str,
) -> ChecklistSummary:
    """Count a checklist's outcomes by status.

    @param specs: the declared items or checks.
    @param results: the evaluated results, one per spec.
    @param result_id: ``"item_id"`` or ``"check_id"`` -- which id the results carry.
    """

    required_ids = {
        getattr(spec, "item_id", getattr(spec, "check_id", ""))
        for spec in specs
        if spec.required
    }
    statuses = {getattr(result, result_id): result.status for result in results}
    return ChecklistSummary(
        total=len(specs),
        required=len(required_ids),
        passed=sum(status is CheckStatus.PASS for status in statuses.values()),
        warned=sum(status is CheckStatus.WARN for status in statuses.values()),
        failed=sum(status is CheckStatus.FAIL for status in statuses.values()),
        unknown=sum(status is CheckStatus.UNKNOWN for status in statuses.values()),
        needs_human=sum(status is CheckStatus.NEEDS_HUMAN for status in statuses.values()),
    )


def read_field(source: Any, path: tuple[str, ...]) -> tuple[bool, Any]:
    """Resolve a field path inside a nested mapping or sequence.

    Returns ``(False, None)`` for a path that is not there. A missing path is
    reported as *unresolved* rather than as a wrong value by every caller, because
    an absent field and a field holding the wrong value are different findings.
    """

    current = source
    for segment in path:
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list) and segment.lstrip("-").isdigit():
            index = int(segment)
            if not -len(current) <= index < len(current):
                return False, None
            current = current[index]
        else:
            return False, None
    return True, current


def require_check_evidence(check: AcceptanceCheck, result: CheckResult) -> CheckResult:
    """Downgrade a pass with no evidence behind it to *unknown*.

    A check marked ``evidence_required`` that reports success while naming no
    evidence is not proof; treating it as a pass would let an assertion stand in
    for a result.
    """

    if (
        check.evidence_required
        and result.status in {CheckStatus.PASS, CheckStatus.WARN}
        and not result.evidence_refs
    ):
        return replace(
            result,
            status=CheckStatus.UNKNOWN,
            reason="required acceptance evidence is missing",
        )
    return result


def apply_check(declared: AcceptanceCheck, value: Any, identifier: str) -> CheckResult:
    """Apply a declared check to a value already read for it.

    The reason text names what was actually compared, because "check failed" on
    its own leaves an author guessing which of a dozen values disagreed.
    """

    operator = declared.operator
    expected = declared.expected

    if operator is CheckOperator.MANUAL:
        return CheckResult(check_id=identifier, status=CheckStatus.NEEDS_HUMAN,
                           actual=value, expected=expected,
                           reason="manual check awaits a human verdict")
    if operator is CheckOperator.EXISTS:
        present = value is not None
        return CheckResult(check_id=identifier,
                           status=CheckStatus.PASS if present else CheckStatus.FAIL,
                           actual=value, expected=expected,
                           reason="present" if present else "absent")
    if operator is CheckOperator.TRUTHY:
        truthy = bool(value)
        return CheckResult(check_id=identifier,
                           status=CheckStatus.PASS if truthy else CheckStatus.FAIL,
                           actual=value, expected=expected,
                           reason="truthy" if truthy else f"falsy: {value!r}")
    if operator is CheckOperator.COUNT_EQUALS:
        try:
            size = len(value)
        except TypeError:
            return CheckResult(check_id=identifier, status=CheckStatus.FAIL,
                               actual=value, expected=expected,
                               reason=f"not countable: {value!r}")
        same = size == expected
        return CheckResult(check_id=identifier,
                           status=CheckStatus.PASS if same else CheckStatus.FAIL,
                           actual=value, expected=expected,
                           reason=f"count {size} vs {expected}")
    if operator is CheckOperator.WITHIN_TOLERANCE:
        if declared.tolerance is None:
            return CheckResult(check_id=identifier, status=CheckStatus.FAIL,
                               actual=value, expected=expected,
                               reason="within_tolerance has no tolerance")
        okay = compare(operator, value, expected, declared.tolerance)
        return CheckResult(check_id=identifier,
                           status=CheckStatus.PASS if okay else CheckStatus.FAIL,
                           actual=value, expected=expected,
                           reason=f"|{value} - {expected}| within {declared.tolerance}")

    passed = compare(operator, value, expected, declared.tolerance)
    return CheckResult(check_id=identifier,
                       status=CheckStatus.PASS if passed else CheckStatus.FAIL,
                       actual=value, expected=expected,
                       reason=f"{value!r} == {expected!r}" if passed
                       else f"{value!r} != {expected!r}")



@dataclass(frozen=True, slots=True)
class StageAcceptance:
    """Deterministic outcome of one STAGE node, derived from evidence."""

    status: CheckStatus
    item_results: tuple[ExecutionItemResult, ...]
    check_results: tuple[CheckResult, ...]
    execution_summary: ChecklistSummary
    acceptance_summary: ChecklistSummary
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    resume_pointer: str | None = None


class StageAcceptanceEvaluator:
    """Judge one STAGE node against its own frozen checklists."""

    def evaluate(
        self,
        node: WorkflowNode,
        path: str,
        execution_results: tuple[ExecutionResult, ...],
        item_results: tuple[ExecutionItemResult, ...] = (),
        check_results: tuple[CheckResult, ...] = (),
    ) -> StageAcceptance:
        """Evaluate one leaf node.

        @param node: the STAGE node to judge.
        @param path: the node's absolute path, which is its identity.
        @param execution_results: the call results the Agent reported for this node.
        @param item_results: execution checklist results the Agent submitted
            explicitly. Only items that derive from no call may be submitted this
            way; the deterministic ones are derived and may not be overridden.
        @param check_results: acceptance check results the Agent submitted
            explicitly. Only ``manual`` checks may be submitted.
        @returns the node's outcome, with every checklist item's own verdict.
        """

        body = node.stage
        if body is None:
            raise ValueError(f"{path}: a STAGE node must carry a stage body")

        tool_by_id = {result.call_id: result for result in execution_results}
        explicit_items = {result.item_id: result for result in item_results}
        explicit_checks = {result.check_id: result for result in check_results}
        declared_checks = tuple(wrapper.check for wrapper in node.declared_checks)

        evaluated_items = tuple(
            self._execution_result(item, tool_by_id, explicit_items.get(item.item_id))
            for item in body.execution_checklist
        )
        evaluated_checks = tuple(
            self._check_result(check, tool_by_id, explicit_checks.get(check.check_id))
            for check in declared_checks
        )
        execution_summary = self._summary(body.execution_checklist, evaluated_items, "item_id")
        acceptance_summary = self._summary(declared_checks, evaluated_checks, "check_id")
        status, warnings, errors = self._stage_status(
            body.execution_checklist,
            declared_checks,
            evaluated_items,
            evaluated_checks,
        )
        return StageAcceptance(
            status=status,
            item_results=evaluated_items,
            check_results=evaluated_checks,
            execution_summary=execution_summary,
            acceptance_summary=acceptance_summary,
            warnings=warnings,
            errors=errors,
            resume_pointer=(
                None
                if status in {CheckStatus.PASS, CheckStatus.WARN}
                else (node.recovery or path)
            ),
        )

    # -- One execution checklist item --

    def _execution_result(
        self,
        item: ExecutionChecklistItem,
        tool_by_id: dict[str, ExecutionResult],
        explicit: ExecutionItemResult | None,
    ) -> ExecutionItemResult:
        if explicit is not None:
            return self._require_execution_evidence(item, explicit)
        if not item.call_ids:
            return ExecutionItemResult(
                item_id=item.item_id,
                status=CheckStatus.UNKNOWN,
                reason="execution checklist item has no execution evidence or explicit result",
            )
        results = tuple(tool_by_id.get(call_id) for call_id in item.call_ids)
        status = self._tool_status(
            tuple(result.status for result in results if result is not None), len(results)
        )
        evidence = tuple(
            f"execution-result:{call_id}"
            for call_id, result in zip(item.call_ids, results)
            if result is not None
        )
        result = ExecutionItemResult(
            item_id=item.item_id,
            status=status,
            call_ids=item.call_ids,
            evidence_refs=evidence,
            reason=self._tool_status_reason(status),
        )
        return self._require_execution_evidence(item, result)

    # -- One acceptance check --

    def _check_result(
        self,
        check: AcceptanceCheck,
        tool_by_id: dict[str, ExecutionResult],
        explicit: CheckResult | None,
    ) -> CheckResult:
        if explicit is not None:
            referenced = check.referenced_call_ids
            if referenced:
                referenced_results = tuple(tool_by_id.get(call_id) for call_id in referenced)
                source_status = self._tool_status(
                    tuple(result.status for result in referenced_results if result is not None),
                    len(referenced_results),
                )
                if source_status not in {CheckStatus.PASS, CheckStatus.WARN}:
                    return CheckResult(
                        check_id=check.check_id,
                        status=source_status,
                        actual=explicit.actual,
                        expected=check.expected,
                        evidence_refs=tuple(
                            f"execution-result:{call_id}"
                            for call_id, result in zip(referenced, referenced_results)
                            if result is not None
                        ),
                        reason="referenced verifier Tool did not produce usable evidence",
                    )
                if explicit.status is CheckStatus.PASS and source_status is CheckStatus.WARN:
                    explicit = replace(explicit, status=CheckStatus.WARN)
            return self._require_check_evidence(check, explicit)
        if check.operator is CheckOperator.MANUAL:
            return CheckResult(
                check_id=check.check_id,
                status=CheckStatus.UNKNOWN,
                expected=check.expected,
                reason="manual or complex acceptance check has no recorded result",
            )

        referenced = check.referenced_call_ids
        referenced_results = tuple(tool_by_id.get(call_id) for call_id in referenced)
        evidence = tuple(
            f"execution-result:{call_id}"
            for call_id, result in zip(referenced, referenced_results)
            if result is not None
        )
        tool_status = self._tool_status(
            tuple(result.status for result in referenced_results if result is not None),
            len(referenced_results),
        )
        if check.operator is CheckOperator.TOOL_SUCCEEDED:
            return self._require_check_evidence(
                check,
                CheckResult(
                    check_id=check.check_id,
                    status=tool_status,
                    actual=[result.status.value for result in referenced_results if result is not None],
                    expected=TaskStatus.SUCCEEDED.value,
                    evidence_refs=evidence,
                    reason=self._tool_status_reason(tool_status),
                ),
            )
        if tool_status not in {CheckStatus.PASS, CheckStatus.WARN}:
            return CheckResult(
                check_id=check.check_id,
                status=tool_status,
                expected=check.expected,
                evidence_refs=evidence,
                reason="source Tool did not produce usable evidence",
            )

        source_id = check.source_call_id or (referenced[0] if len(referenced) == 1 else None)
        source = tool_by_id.get(source_id) if source_id else None
        if source is None:
            return CheckResult(
                check_id=check.check_id,
                status=CheckStatus.UNKNOWN,
                expected=check.expected,
                evidence_refs=evidence,
                reason="acceptance check has no unique source ExecutionResult",
            )
        found, actual = read_field(source.evidence_view(), check.actual_path)
        if not found:
            return CheckResult(
                check_id=check.check_id,
                status=CheckStatus.UNKNOWN,
                expected=check.expected,
                evidence_refs=evidence,
                reason=f"ExecutionResult output path is missing: {'.'.join(check.actual_path)}",
            )
        passed = self._compare(check.operator, actual, check.expected, check.tolerance)
        status = CheckStatus.PASS if passed else CheckStatus.FAIL
        if passed and tool_status is CheckStatus.WARN:
            status = CheckStatus.WARN
        return self._require_check_evidence(
            check,
            CheckResult(
                check_id=check.check_id,
                status=status,
                actual=actual,
                expected=check.expected,
                evidence_refs=evidence,
                reason="acceptance condition satisfied" if passed else "acceptance condition not satisfied",
            ),
        )

    # -- Shared helpers, also used for composite checks --

    @staticmethod
    def _tool_status(statuses: tuple[TaskStatus, ...], expected_count: int) -> CheckStatus:
        if TaskStatus.NEEDS_APPROVAL in statuses:
            return CheckStatus.NEEDS_HUMAN
        if TaskStatus.FAILED in statuses:
            return CheckStatus.FAIL
        if len(statuses) != expected_count or not statuses:
            return CheckStatus.UNKNOWN
        if any(
            status in {TaskStatus.BLOCKED, TaskStatus.PLANNED, TaskStatus.RUNNING}
            for status in statuses
        ):
            return CheckStatus.UNKNOWN
        if TaskStatus.DEGRADED in statuses:
            return CheckStatus.WARN
        return CheckStatus.PASS

    @staticmethod
    def _tool_status_reason(status: CheckStatus) -> str:
        return {
            CheckStatus.PASS: "all referenced Tool Calls succeeded",
            CheckStatus.WARN: "referenced Tool Calls completed with warnings",
            CheckStatus.FAIL: "a referenced Tool Call failed",
            CheckStatus.UNKNOWN: "referenced Tool evidence is missing or incomplete",
            CheckStatus.NEEDS_HUMAN: "a referenced Tool Call requires human approval",
        }[status]

    @staticmethod
    def _require_execution_evidence(
        item: ExecutionChecklistItem,
        result: ExecutionItemResult,
    ) -> ExecutionItemResult:
        if (
            item.evidence_required
            and result.status in {CheckStatus.PASS, CheckStatus.WARN}
            and not result.evidence_refs
        ):
            return replace(
                result,
                status=CheckStatus.UNKNOWN,
                reason="required execution evidence is missing",
            )
        return result

    @staticmethod
    def _require_check_evidence(check: AcceptanceCheck, result: CheckResult) -> CheckResult:
        return require_check_evidence(check, result)

    @staticmethod
    def read_path(outputs: dict[str, Any], path: tuple[str, ...]) -> tuple[bool, Any]:
        """Alias for :func:`read_field`, which is the one implementation."""

        return read_field(outputs, path)

    @classmethod
    def _compare(
        cls,
        operator: CheckOperator,
        actual: Any,
        expected: Any,
        tolerance: float | None,
    ) -> bool:
        return compare(operator, actual, expected, tolerance)

    @staticmethod
    def _summary(
        specs: tuple[Any, ...],
        results: tuple[Any, ...],
        result_id: str,
    ) -> ChecklistSummary:
        return summarise_checklist(specs, results, result_id)

    @staticmethod
    def _stage_status(
        execution_items: tuple[ExecutionChecklistItem, ...],
        checks: tuple[AcceptanceCheck, ...],
        item_results: tuple[ExecutionItemResult, ...],
        check_results: tuple[CheckResult, ...],
    ) -> tuple[CheckStatus, tuple[str, ...], tuple[str, ...]]:
        """Decide the leaf's verdict from its required items and checks.

        A required item that is merely unresolved blocks; only an explicit FAIL
        fails. ``needs_human`` outranks everything: a human decision stops the run
        harder than a retryable failure does.
        """

        execution_specs = {item.item_id: item for item in execution_items}
        acceptance_specs = {check.check_id: check for check in checks}
        # Items and checks are kept apart so a message can say which it means: an
        # execution item reported as a "failed check" sends an author looking in
        # the wrong list.
        required_items = [
            (result.item_id, result.status)
            for result in item_results
            if execution_specs[result.item_id].required
        ]
        required_checks = [
            (result.check_id, result.status)
            for result in check_results
            if acceptance_specs[result.check_id].required
        ]
        optional_issues = [
            (result.item_id, result.status)
            for result in item_results
            if not execution_specs[result.item_id].required and result.status is not CheckStatus.PASS
        ] + [
            (result.check_id, result.status)
            for result in check_results
            if not acceptance_specs[result.check_id].required and result.status is not CheckStatus.PASS
        ]

        def matching(status: CheckStatus) -> tuple[str, ...]:
            return tuple(
                [f"{item_id} (item)" for item_id, s in required_items if s is status]
                + [f"{check_id} (check)" for check_id, s in required_checks if s is status]
            )

        human = matching(CheckStatus.NEEDS_HUMAN)
        if human:
            return CheckStatus.NEEDS_HUMAN, (), (
                "required Stage work needs human judgment: " + ", ".join(human),
            )
        failed = matching(CheckStatus.FAIL)
        if failed:
            return CheckStatus.FAIL, (), (
                "required Stage work failed: " + ", ".join(failed),
            )
        unknown = matching(CheckStatus.UNKNOWN)
        if unknown:
            return CheckStatus.UNKNOWN, (), (
                "required Stage work lacks evidence: " + ", ".join(unknown),
            )
        warned = matching(CheckStatus.WARN)
        if warned or optional_issues:
            warnings = tuple(
                [f"required Stage work completed with warning: {name}" for name in warned]
                + [
                    f"non-blocking checklist result: {item_id}={status.value}"
                    for item_id, status in optional_issues
                ]
            )
            return CheckStatus.WARN, warnings, ()
        return CheckStatus.PASS, (), ()
