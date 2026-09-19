"""The four gaps found while auditing the flow, pinned so they stay closed.

    A result that omits its target was accepted, so a call could silently run
    against a different server than the Workflow declared.

    `finish` reported `blocked` with an empty `errors`, so the Agent learned it
    was stuck but not what it was waiting for.

    A rejected `item` or `check` printed an empty `detail`, so the caller could
    not tell which one it was.

    `status` showed no Workflow, so the Agent had to re-read the file it authored
    -- which it may have edited, or lost with the process.
"""

import json

import pytest

from ainative.cli import commands as session_cli
from ainative.cli.output import EXIT_BLOCKING, EXIT_OK, EXIT_UNUSABLE
from ainative.reading import workflow_from_dict

ENVELOPE_KEYS = ["command", "ok", "verdict", "exit_code", "detail", "errors"]


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _stage(stage_id, call_id, tool, *, manual_check=False):
    checks = [
        {"check_id": f"k-{stage_id}", "description": "ok", "operator": "tool_succeeded",
         "source_call_id": call_id, "call_ids": [call_id]}
    ]
    if manual_check:
        checks.append({"check_id": f"m-{stage_id}", "description": "sign-off",
                       "operator": "manual"})
    return {
        "node_id": stage_id,
        "kind": "stage",
        "purpose": f"{stage_id} goal",
        "stage": {
            "stage_kind": "change",
            "calls": [{"call_id": call_id, "target": {"owner": "ue5", "name": tool}}],
            "execution_checklist": [
                {"item_id": f"i-{stage_id}", "description": "ran", "call_ids": [call_id]}
            ],
            "acceptance_checklist": checks,
        },
    }


def _workflow(stages):
    return {
        "workflow_id": "t:workflow",
        "guidance": "host-operation",
        "revision": 1,
        "root": {"node_id": "work", "kind": "workflow", "purpose": "work",
                 "children": stages},
    }


WORKFLOW = _workflow([
    _stage("a", "a1", "do_a", manual_check=True),
    _stage("b", "b1", "do_b"),
])


def _stage_paths() -> dict[str, str]:
    workflow = workflow_from_dict(WORKFLOW)
    return {node.node_id: path for path, node in workflow.stages}


@pytest.fixture
def workspace(tmp_path, capsys):
    state = str(tmp_path / "state.json")
    task = _write(tmp_path / "task.json", {
        "task_id": "t", "objective": "o", "guidance": "host-operation",
    })
    workflow = _write(tmp_path / "wf.json", WORKFLOW)

    session_cli.main(["--state", state, "--task", task, "--workflow", workflow, "open"])
    opened = json.loads(capsys.readouterr().out)

    def run(*args):
        code = session_cli.main(["--state", state, *args])
        return code, json.loads(capsys.readouterr().out)

    def record(body):
        return run("--result", _write(tmp_path / "r.json", body), "record")

    return {
        "state": state, "tmp": tmp_path, "open": opened, "run": run, "record": record,
        "paths": _stage_paths(),
    }


# --- gap 1: the target is not optional -----------------------------------------


def test_a_result_without_a_target_is_refused(workspace):
    code, payload = workspace["record"]({"call_id": "a1", "status": "succeeded"})

    assert code == EXIT_UNUSABLE
    assert list(payload) == ENVELOPE_KEYS
    assert "must report the target it ran" in payload["errors"][0]


def test_a_result_naming_the_wrong_server_is_refused(workspace):
    code, payload = workspace["record"]({
        "call_id": "a1", "status": "succeeded",
        "target": {"owner": "blender", "name": "do_a"},
    })

    assert code == EXIT_UNUSABLE
    assert "target mismatch" in payload["errors"][0]


def test_a_result_naming_the_wrong_tool_is_refused(workspace):
    code, payload = workspace["record"]({
        "call_id": "a1", "status": "succeeded",
        "target": {"owner": "ue5", "name": "something_else"},
    })

    assert code == EXIT_UNUSABLE
    assert "target mismatch" in payload["errors"][0]


def test_the_declared_target_is_accepted(workspace):
    code, payload = workspace["record"]({
        "call_id": "a1", "status": "succeeded",
        "target": {"owner": "ue5", "name": "do_a"},
    })

    assert code == EXIT_OK
    assert payload["verdict"] == "succeeded"


# --- gap 2: finish names what is outstanding -----------------------------------


def test_finish_names_the_stages_that_are_not_closed(workspace):
    code, payload = workspace["run"]("finish")

    assert code == EXIT_BLOCKING
    assert payload["verdict"] == "blocked"
    assert "required nodes not closed" in payload["errors"][0]
    assert workspace["paths"]["a"] in payload["errors"][0]
    assert workspace["paths"]["b"] in payload["errors"][0]
    workflow = workflow_from_dict(WORKFLOW)
    assert payload["detail"]["details"]["outstanding_nodes"] == [
        *workflow.composite_paths, *workflow.stage_paths]


def test_finish_reports_nothing_outstanding_once_everything_closes(workspace):
    workspace["record"]({"call_id": "a1", "status": "succeeded",
                         "target": {"owner": "ue5", "name": "do_a"}})
    workspace["run"]("--result", _write(workspace["tmp"] / "m.json", {
        "check_id": "m-a", "status": "pass", "evidence_refs": ["human:ok"]}), "check")
    workspace["run"]("--stage", workspace["paths"]["a"], "stage")
    workspace["record"]({"call_id": "b1", "status": "succeeded",
                         "target": {"owner": "ue5", "name": "do_b"}})
    workspace["run"]("--stage", workspace["paths"]["b"], "stage")

    code, payload = workspace["run"]("finish")

    assert code == EXIT_OK
    assert payload["detail"]["details"]["outstanding_nodes"] == []


# --- gap 3: a rejected item or check still names itself ------------------------


def test_a_rejected_item_still_names_the_item(workspace):
    code, payload = workspace["run"]("--result", _write(workspace["tmp"] / "i.json", {
        "item_id": "not-declared", "status": "pass"}), "item")

    assert code == EXIT_UNUSABLE
    assert list(payload) == ENVELOPE_KEYS
    assert payload["detail"]["item_id"] == "not-declared"
    assert payload["detail"]["status"] == "pass"


def test_a_rejected_check_still_names_the_check(workspace):
    code, payload = workspace["run"]("--result", _write(workspace["tmp"] / "c.json", {
        "check_id": "not-declared", "status": "pass"}), "check")

    assert code == EXIT_UNUSABLE
    assert payload["detail"]["check_id"] == "not-declared"
    assert payload["detail"]["status"] == "pass"


def test_an_accepted_item_names_its_stage(workspace):
    code, payload = workspace["run"]("--result", _write(workspace["tmp"] / "i.json", {
        "item_id": "i-b", "status": "pass", "evidence_refs": ["x"]}), "item")

    # i-b declares a call, so it is derived and cannot be submitted.
    assert code == EXIT_UNUSABLE
    assert payload["detail"]["node_path"] == workspace["paths"]["b"]


# --- gap 4: status lets the Agent read back its Workflow -----------------------


def _stages(summary):
    return [node for node in summary["nodes"] if node["kind"] == "stage"]


def test_status_describes_the_bound_workflow(workspace):
    _, payload = workspace["run"]("status")
    summary = payload["detail"]["workflow"]

    assert summary["workflow_id"] == "t:workflow"
    assert summary["revision"] == 1
    assert summary["guidance"] == "host-operation"
    assert [s["node_id"] for s in _stages(summary)] == ["a", "b"]


def test_status_lists_each_stage_call_and_check(workspace):
    _, payload = workspace["run"]("status")
    stages = {s["node_id"]: s for s in _stages(payload["detail"]["workflow"])}

    assert [c["call_id"] for c in stages["a"]["calls"]] == ["a1"]
    assert stages["a"]["calls"][0]["target"] == {"owner": "ue5", "name": "do_a"}
    assert [c["check_id"] for c in stages["a"]["acceptance_checklist"]] == ["k-a", "m-a"]
    assert [i["item_id"] for i in stages["a"]["execution_checklist"]] == ["i-a"]


def test_status_marks_closure_and_side_effects(workspace):
    before = _stages(workspace["run"]("status")[1]["detail"]["workflow"])
    assert all(not s["closed"] and not s["side_effects_recorded"] for s in before)

    workspace["record"]({"call_id": "a1", "status": "succeeded",
                         "target": {"owner": "ue5", "name": "do_a"}})
    workspace["run"]("--result", _write(workspace["tmp"] / "m.json", {
        "check_id": "m-a", "status": "pass", "evidence_refs": ["human:ok"]}), "check")
    workspace["run"]("--stage", workspace["paths"]["a"], "stage")

    after = {s["node_id"]: s for s in
             _stages(workspace["run"]("status")[1]["detail"]["workflow"])}
    assert after["a"]["closed"] is True
    assert after["a"]["side_effects_recorded"] is True
    assert after["b"]["closed"] is False


def test_status_no_longer_requires_reading_the_workflow_file(workspace):
    """Everything needed to act is in the envelope: calls, checks, and closure."""

    _, payload = workspace["run"]("status")
    summary = payload["detail"]["workflow"]

    for stage in _stages(summary):
        assert stage["calls"], "a Stage must show what it will invoke"
        assert stage["acceptance_checklist"], "a Stage must show what it must prove"
        assert "closed" in stage
