from __future__ import annotations

from dataclasses import dataclass, replace
from math import isclose
from typing import Any

from ainative.orchestration.contracts.checklists import (
    AcceptanceCheck,
    ChecklistSummary,
    CheckOperator,
    CheckResult,
    CheckStatus,
    ExecutionChecklistItem,
    ExecutionItemResult,
)
from ainative.orchestration.contracts.plan import StageRequest
from ainative.orchestration.contracts.results import ExecutionResult, TaskStatus


@dataclass(frozen=True, slots=True)
class StageAcceptance:
    """Deterministic Stage outcome derived from checklists and evidence."""

    status: TaskStatus
    execution_results: tuple[ExecutionItemResult, ...]
    check_results: tuple[CheckResult, ...]
    execution_summary: ChecklistSummary
    acceptance_summary: ChecklistSummary
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    resume_pointer: str | None = None


class StageAcceptanceEvaluator:
    """Evaluate Stage checklists without discovering or invoking Tools."""

    def evaluate(
        self,
        stage: StageRequest,
        execution_results: tuple[ExecutionResult, ...],
        execution_item_results: tuple[ExecutionItemResult, ...] = (),
        check_results: tuple[CheckResult, ...] = (),
    ) -> StageAcceptance:
        tool_by_id = {result.call_id: result for result in execution_results}
        explicit_execution = {result.item_id: result for result in execution_item_results}
        explicit_checks = {result.check_id: result for result in check_results}

        evaluated_execution = tuple(
            self._execution_result(item, tool_by_id, explicit_execution.get(item.item_id))
            for item in stage.execution_checklist
        )
        evaluated_checks = tuple(
            self._check_result(check, tool_by_id, explicit_checks.get(check.check_id))
            for check in stage.acceptance_checklist
        )
        execution_summary = self._summary(stage.execution_checklist, evaluated_execution, "item_id")
        acceptance_summary = self._summary(stage.acceptance_checklist, evaluated_checks, "check_id")
        status, warnings, errors = self._stage_status(
            stage,
            evaluated_execution,
            evaluated_checks,
        )
        return StageAcceptance(
            status=status,
            execution_results=evaluated_execution,
            check_results=evaluated_checks,
            execution_summary=execution_summary,
            acceptance_summary=acceptance_summary,
            warnings=warnings,
            errors=errors,
            resume_pointer=None if status in {TaskStatus.SUCCEEDED, TaskStatus.DEGRADED} else (stage.recovery or stage.stage_id),
        )

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
        status = self._tool_status(tuple(result.status for result in results if result is not None), len(results))
        evidence = tuple(f"execution-result:{call_id}" for call_id, result in zip(item.call_ids, results) if result is not None)
        result = ExecutionItemResult(
            item_id=item.item_id,
            status=status,
            call_ids=item.call_ids,
            evidence_refs=evidence,
            reason=self._tool_status_reason(status),
        )
        return self._require_execution_evidence(item, result)

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
        evidence = tuple(f"execution-result:{call_id}" for call_id, result in zip(referenced, referenced_results) if result is not None)
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
        found, actual = self._read_path(source.outputs, check.actual_path)
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

    @staticmethod
    def _tool_status(statuses: tuple[TaskStatus, ...], expected_count: int) -> CheckStatus:
        if TaskStatus.NEEDS_APPROVAL in statuses:
            return CheckStatus.NEEDS_HUMAN
        if TaskStatus.FAILED in statuses:
            return CheckStatus.FAIL
        if len(statuses) != expected_count or not statuses:
            return CheckStatus.UNKNOWN
        if any(status in {TaskStatus.BLOCKED, TaskStatus.PLANNED, TaskStatus.RUNNING} for status in statuses):
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
        if item.evidence_required and result.status in {CheckStatus.PASS, CheckStatus.WARN} and not result.evidence_refs:
            return replace(
                result,
                status=CheckStatus.UNKNOWN,
                reason="required execution evidence is missing",
            )
        return result

    @staticmethod
    def _require_check_evidence(check: AcceptanceCheck, result: CheckResult) -> CheckResult:
        if check.evidence_required and result.status in {CheckStatus.PASS, CheckStatus.WARN} and not result.evidence_refs:
            return replace(
                result,
                status=CheckStatus.UNKNOWN,
                reason="required acceptance evidence is missing",
            )
        return result

    @staticmethod
    def _read_path(outputs: dict[str, Any], path: tuple[str, ...]) -> tuple[bool, Any]:
        value: Any = outputs
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return False, None
            value = value[key]
        return True, value

    @classmethod
    def _compare(
        cls,
        operator: CheckOperator,
        actual: Any,
        expected: Any,
        tolerance: float | None,
    ) -> bool:
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
            return cls._within_tolerance(actual, expected, tolerance)
        return False

    @classmethod
    def _within_tolerance(cls, actual: Any, expected: Any, tolerance: float | None) -> bool:
        selected_tolerance = 1e-6 if tolerance is None else float(tolerance)
        if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
            return len(actual) == len(expected) and all(
                cls._within_tolerance(left, right, selected_tolerance)
                for left, right in zip(actual, expected)
            )
        try:
            return isclose(float(actual), float(expected), abs_tol=selected_tolerance, rel_tol=0.0)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _summary(specs: tuple[Any, ...], results: tuple[Any, ...], result_id: str) -> ChecklistSummary:
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

    @staticmethod
    def _stage_status(
        stage: StageRequest,
        execution_results: tuple[ExecutionItemResult, ...],
        check_results: tuple[CheckResult, ...],
    ) -> tuple[TaskStatus, tuple[str, ...], tuple[str, ...]]:
        execution_specs = {item.item_id: item for item in stage.execution_checklist}
        acceptance_specs = {check.check_id: check for check in stage.acceptance_checklist}
        required_results = [
            (result.item_id, result.status)
            for result in execution_results
            if execution_specs[result.item_id].required
        ] + [
            (result.check_id, result.status)
            for result in check_results
            if acceptance_specs[result.check_id].required
        ]
        optional_issues = [
            (result.item_id, result.status)
            for result in execution_results
            if not execution_specs[result.item_id].required and result.status is not CheckStatus.PASS
        ] + [
            (result.check_id, result.status)
            for result in check_results
            if not acceptance_specs[result.check_id].required and result.status is not CheckStatus.PASS
        ]

        def matching(status: CheckStatus) -> tuple[str, ...]:
            return tuple(item_id for item_id, result_status in required_results if result_status is status)

        human = matching(CheckStatus.NEEDS_HUMAN)
        if human:
            return TaskStatus.NEEDS_APPROVAL, (), (
                "required Stage checks need human judgment: " + ", ".join(human),
            )
        failed = matching(CheckStatus.FAIL)
        if failed:
            return TaskStatus.FAILED, (), (
                "required Stage checks failed: " + ", ".join(failed),
            )
        unknown = matching(CheckStatus.UNKNOWN)
        if unknown:
            return TaskStatus.BLOCKED, (), (
                "required Stage checks lack evidence: " + ", ".join(unknown),
            )
        warned = matching(CheckStatus.WARN)
        if warned or optional_issues:
            warnings = tuple(
                [f"required Stage check completed with warning: {item_id}" for item_id in warned]
                + [f"non-blocking checklist result: {item_id}={status.value}" for item_id, status in optional_issues]
            )
            return TaskStatus.DEGRADED, warnings, ()
        return TaskStatus.SUCCEEDED, (), ()
