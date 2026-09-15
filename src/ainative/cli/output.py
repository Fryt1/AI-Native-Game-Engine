"""The one output shape every CLI command prints.

A caller — an Agent, a shell script, a test — should be able to read the verdict
without knowing which command ran or how deep the payload nests. So every command
prints the same envelope, with the same keys in the same order:

    command    which command produced this
    ok         whether the command reached a non-blocking outcome
    verdict    one word for what happened, from a single vocabulary
    exit_code  the process exit code, repeated so a caller never has to read it
    detail     the command's own payload, always present
    errors     always a list; empty on success

`verdict` uses one vocabulary for every command. Stage and Task outcomes already
speak `TaskStatus`; a checklist item's `CheckStatus` is mapped onto it, so a
caller matches one set of words:

    pass          -> succeeded
    warn          -> degraded
    fail          -> failed
    unknown       -> blocked
    needs_human   -> needs_approval
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from ainative.model.checklists import CheckStatus
from ainative.model.results import TaskStatus

# Exit codes. 0 non-blocking, 1 blocking or failing, 2 the command could not run.
EXIT_OK = 0
EXIT_BLOCKING = 1
EXIT_UNUSABLE = 2


class Verdict(StrEnum):
    """What happened, in the one vocabulary every command shares."""

    SUCCEEDED = "succeeded"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    FAILED = "failed"
    NEEDS_APPROVAL = "needs_approval"


# A verdict in this set means the workflow cannot proceed.
BLOCKING_VERDICTS = frozenset({
    Verdict.BLOCKED,
    Verdict.FAILED,
    Verdict.NEEDS_APPROVAL,
})

# A TaskStatus that can appear on a *result*. PLANNED and RUNNING describe a task
# still in flight; nothing in this repository emits them as an outcome, so they
# have no verdict. Mapping one is a programming error, not a runtime condition.
_RESULT_TO_VERDICT = {
    TaskStatus.SUCCEEDED: Verdict.SUCCEEDED,
    TaskStatus.DEGRADED: Verdict.DEGRADED,
    TaskStatus.FAILED: Verdict.FAILED,
    TaskStatus.BLOCKED: Verdict.BLOCKED,
    TaskStatus.NEEDS_APPROVAL: Verdict.NEEDS_APPROVAL,
}

# A checklist outcome, expressed in the shared vocabulary.
_CHECK_TO_VERDICT = {
    CheckStatus.PASS: Verdict.SUCCEEDED,
    CheckStatus.WARN: Verdict.DEGRADED,
    CheckStatus.FAIL: Verdict.FAILED,
    CheckStatus.UNKNOWN: Verdict.BLOCKED,
    CheckStatus.NEEDS_HUMAN: Verdict.NEEDS_APPROVAL,
}


def verdict_for_task_status(status: TaskStatus) -> Verdict:
    """Map a Stage or Task outcome onto the shared verdict.

    @param status: the outcome of a Stage or Task.
    @returns the shared verdict.
    @throws KeyError when the status is not an outcome (see `_RESULT_TO_VERDICT`).
    """

    return _RESULT_TO_VERDICT[status]


def verdict_for_check_status(status: CheckStatus) -> Verdict:
    """Map a checklist outcome onto the shared verdict."""

    return _CHECK_TO_VERDICT[status]


def exit_code_for(verdict: Verdict) -> int:
    """Return the process exit code for a verdict."""

    return EXIT_BLOCKING if verdict in BLOCKING_VERDICTS else EXIT_OK


def envelope(
    command: str,
    *,
    verdict: Verdict,
    detail: dict[str, Any] | None = None,
    errors: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    """Build the output envelope every command prints.

    @param command: the command that produced this output.
    @param verdict: what happened, in the shared vocabulary.
    @param detail: the command's own payload; omitted becomes an empty object.
    @param errors: what went wrong, if anything.
    @returns the envelope, with keys in a fixed order.
    """

    code = exit_code_for(verdict)
    return {
        "command": command,
        "ok": code == EXIT_OK,
        "verdict": verdict.value,
        "exit_code": code,
        "detail": detail if detail is not None else {},
        "errors": list(errors),
    }


def unusable(command: str, *errors: str) -> tuple[dict[str, Any], int]:
    """Build the envelope for a command that could not run at all.

    The Workflow and the recorded evidence are untouched; the command itself
    failed, so the caller can fix its input and retry.

    @param command: the command that was attempted.
    @param errors: one message per problem found.
    @returns the envelope and the exit code, ready to return from `main`.
    """

    payload = envelope(command, verdict=Verdict.BLOCKED, errors=errors)
    payload["ok"] = False
    payload["exit_code"] = EXIT_UNUSABLE
    return payload, EXIT_UNUSABLE


def emit(payload: dict[str, Any]) -> None:
    """Print one envelope as JSON."""

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
