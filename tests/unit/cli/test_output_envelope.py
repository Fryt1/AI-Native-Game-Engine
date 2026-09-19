"""The CLI output envelope is a contract, so it is tested as one.

Every command must print the same six keys in the same order, agree between its
`exit_code` field and its process exit code, and speak one verdict vocabulary.
A caller should never have to know which command ran, or how deep the payload
nests, to read the outcome.
"""

import json

import pytest

from ainative.cli import commands as session_cli
from ainative.cli.output import (
    BLOCKING_VERDICTS,
    EXIT_BLOCKING,
    EXIT_OK,
    EXIT_UNUSABLE,
    Verdict,
    envelope,
    exit_code_for,
    unusable,
    verdict_for_check_status,
    verdict_for_task_status,
)
from ainative.model.checklists import CheckStatus
from ainative.model.results import TaskStatus

ENVELOPE_KEYS = ["command", "ok", "verdict", "exit_code", "detail", "errors"]


# --- the envelope itself -------------------------------------------------------


def test_the_envelope_has_a_fixed_key_order():
    """Key order is part of the contract: `detail` and `errors` are always last."""

    assert list(envelope("open", verdict=Verdict.SUCCEEDED)) == ENVELOPE_KEYS
    assert list(envelope("stage", verdict=Verdict.FAILED, errors=("boom",))) == ENVELOPE_KEYS


def test_a_success_envelope_is_ok_with_no_errors():
    payload = envelope("record", verdict=Verdict.SUCCEEDED, detail={"call_id": "c"})

    assert payload["ok"] is True
    assert payload["exit_code"] == EXIT_OK
    assert payload["errors"] == []


def test_detail_is_always_an_object_even_when_omitted():
    """A caller can index detail without checking for null."""

    assert envelope("finish", verdict=Verdict.SUCCEEDED)["detail"] == {}


def test_errors_is_always_a_list():
    assert envelope("item", verdict=Verdict.SUCCEEDED)["errors"] == []
    assert envelope("item", verdict=Verdict.FAILED, errors=("one", "two"))["errors"] == ["one", "two"]


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        (Verdict.SUCCEEDED, EXIT_OK),
        (Verdict.DEGRADED, EXIT_OK),
        (Verdict.BLOCKED, EXIT_BLOCKING),
        (Verdict.FAILED, EXIT_BLOCKING),
        (Verdict.NEEDS_APPROVAL, EXIT_BLOCKING),
    ],
)
def test_exit_code_follows_the_verdict(verdict, expected):
    assert exit_code_for(verdict) == expected


def test_ok_agrees_with_the_exit_code():
    for verdict in Verdict:
        payload = envelope("status", verdict=verdict)
        assert payload["ok"] is (payload["exit_code"] == EXIT_OK)


def test_a_degraded_result_is_not_blocking():
    """A warning-only outcome proceeds; it must not stop the loop."""

    payload = envelope("finish", verdict=Verdict.DEGRADED)

    assert payload["ok"] is True
    assert payload["exit_code"] == EXIT_OK
    assert Verdict.DEGRADED not in BLOCKING_VERDICTS


# --- the shared vocabulary -----------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (TaskStatus.SUCCEEDED, Verdict.SUCCEEDED),
        (TaskStatus.DEGRADED, Verdict.DEGRADED),
        (TaskStatus.FAILED, Verdict.FAILED),
        (TaskStatus.BLOCKED, Verdict.BLOCKED),
        (TaskStatus.NEEDS_APPROVAL, Verdict.NEEDS_APPROVAL),
    ],
)
def test_stage_and_task_status_map_onto_the_verdict(status, expected):
    assert verdict_for_task_status(status) is expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (CheckStatus.PASS, Verdict.SUCCEEDED),
        (CheckStatus.WARN, Verdict.DEGRADED),
        (CheckStatus.FAIL, Verdict.FAILED),
        (CheckStatus.UNKNOWN, Verdict.BLOCKED),
        (CheckStatus.NEEDS_HUMAN, Verdict.NEEDS_APPROVAL),
    ],
)
def test_checklist_outcomes_map_onto_the_same_verdict(status, expected):
    """The whole point: a checklist result and a Stage result read the same way."""

    assert verdict_for_check_status(status) is expected


def test_every_outcome_maps_to_a_verdict():
    """A new outcome status must not silently fall through the mapping."""

    for status in CheckStatus:
        assert isinstance(verdict_for_check_status(status), Verdict)

    for status in TaskStatus:
        if status in {TaskStatus.PLANNED, TaskStatus.RUNNING}:
            continue  # in-flight states, never emitted as an outcome
        assert isinstance(verdict_for_task_status(status), Verdict)


def test_an_in_flight_status_has_no_verdict():
    """PLANNED and RUNNING are not outcomes, so mapping one is a programming error."""

    for status in (TaskStatus.PLANNED, TaskStatus.RUNNING):
        with pytest.raises(KeyError):
            verdict_for_task_status(status)


# --- the unusable path ---------------------------------------------------------


def test_unusable_reports_a_distinct_exit_code():
    """Exit 2 means the command could not run, which is not the same as blocked."""

    payload, code = unusable("stage", "state file does not exist")

    assert code == EXIT_UNUSABLE
    assert payload["exit_code"] == EXIT_UNUSABLE
    assert payload["ok"] is False
    assert payload["errors"] == ["state file does not exist"]
    assert payload["command"] == "stage"
    assert list(payload) == ENVELOPE_KEYS


# --- end to end through the CLI ------------------------------------------------


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _workflow_doc():
    return {
        "guidance": "host-operation",
        "route": "host_operation",
        "workflow_id": "v:workflow",
        "root": {
            "node_id": "s",
            "kind": "workflow",
            "purpose": "Move",
            "children": [
                {
                    "node_id": "stage.m",
                    "kind": "stage",
                    "purpose": "Move",
                    "stage": {
                        "stage_kind": "change",
                        "calls": [
                            {"call_id": "m1", "target": {"owner": "ue5", "name": "set_actor_transform"}}
                        ],
                        "execution_checklist": [
                            {"item_id": "ran", "description": "ran", "call_ids": ["m1"]}
                        ],
                        "acceptance_checklist": [
                            {
                                "check_id": "ok",
                                "description": "ok",
                                "operator": "tool_succeeded",
                                "source_call_id": "m1",
                                "call_ids": ["m1"],
                            }
                        ],
                    },
                }
            ],
        },
    }


def _stage_path() -> str:
    from ainative.reading import workflow_from_dict

    return workflow_from_dict(_workflow_doc()).stage_paths[0]


@pytest.fixture
def workspace(tmp_path, capsys):
    state = str(tmp_path / "state.json")
    task = _write(tmp_path / "task.json", {
        "task_id": "v", "objective": "Move", "route": "host_operation",
        "guidance": "host-operation",
    })
    workflow = _write(tmp_path / "workflow.json", _workflow_doc())

    code = session_cli.main(["--state", state, "--task", task, "--workflow", workflow, "open"])
    opened = json.loads(capsys.readouterr().out)

    return {
        "state": state, "tmp": tmp_path, "code": code, "open": opened,
        "capsys": capsys, "workflow": workflow, "task": task,
    }


def test_open_prints_the_envelope(workspace):
    payload = workspace["open"]

    assert list(payload) == ENVELOPE_KEYS
    assert payload["command"] == "open"
    assert payload["verdict"] == "succeeded"
    assert payload["exit_code"] == EXIT_OK
    assert payload["detail"]["ready"] is True
    assert payload["errors"] == []


def test_every_command_prints_the_same_envelope(workspace):
    """The whole loop, checked for shape rather than for content."""

    capsys = workspace["capsys"]
    calls = [
        (["--state", workspace["state"], "--result", _write(workspace["tmp"] / "r.json", {
            "call_id": "m1", "status": "succeeded",
            "target": {"owner": "ue5", "name": "set_actor_transform"}}), "record"]),
        (["--state", workspace["state"], "--result", _write(workspace["tmp"] / "i.json", {
            "item_id": "ran", "status": "pass"}), "item"]),
        (["--state", workspace["state"], "--stage", _stage_path(), "stage"]),
        (["--state", workspace["state"], "finish"]),
        (["--state", workspace["state"], "status"]),
    ]

    for args in calls:
        code = session_cli.main(args)
        payload = json.loads(capsys.readouterr().out)

        assert list(payload) == ENVELOPE_KEYS, args[-1]
        assert payload["exit_code"] == code, args[-1]
        assert payload["ok"] is (code == EXIT_OK), args[-1]
        assert payload["verdict"] in {v.value for v in Verdict}, args[-1]


def test_a_missing_state_file_is_unusable_not_blocked(workspace):
    code = session_cli.main(["--state", str(workspace["tmp"] / "absent.json"), "status"])
    payload = json.loads(workspace["capsys"].readouterr().out)

    assert code == EXIT_UNUSABLE
    assert list(payload) == ENVELOPE_KEYS
    assert payload["exit_code"] == EXIT_UNUSABLE
    assert payload["errors"]
