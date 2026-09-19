"""End-to-end test of the Agent acceptance loop through the session CLI."""

import json
from pathlib import Path

import pytest

from ainative.cli import commands as session_cli
from ainative.reading import workflow_from_dict

TASK = {
    "task_id": "loop-1",
    "objective": "Validate the transferred asset",
    "route": "asset_transfer",
    "source_context": {"app": "ue5"},
    "target_context": {"app": "ue5"},
    "preserve_relations": ["asset_identity"],
}

PLAN = {
    "guidance": "asset-roundtrip",
    "route": "asset_transfer",
    "workflow_id": "loop-1:workflow",
    "root": {
        "node_id": "validate",
        "kind": "workflow",
        "purpose": "Validate",
        "children": [
            {
                "node_id": "stage.validate_asset",
                "kind": "stage",
                "purpose": "Validate result",
                "stage": {
                    "stage_kind": "change",
                    "calls": [
                        {
                            "call_id": "v1",
                            "target": {"owner": "blender", "name": "read_scene"},
                        }
                    ],
                    "execution_checklist": [
                        {"item_id": "run-validator", "description": "run the validator", "call_ids": ["v1"]}
                    ],
                    "acceptance_checklist": [
                        {
                            "check_id": "relations-proven",
                            "description": "required relations have evidence",
                            "operator": "truthy",
                            "source_call_id": "v1",
                            "actual_path": ["preserved_relations"],
                        }
                    ],
                },
            }
        ],
    },
}


def _plan_workflow():
    return workflow_from_dict(PLAN)


def _stage_path() -> str:
    return _plan_workflow().stage_paths[0]


def _completed_paths() -> list[str]:
    workflow = _plan_workflow()
    return [*workflow.composite_paths, *workflow.stage_paths]


def _write(path: Path, document) -> str:
    path.write_text(json.dumps(document), encoding="utf-8")
    return str(path)


@pytest.fixture
def workspace(tmp_path: Path):
    return {
        "state": str(tmp_path / "state.json"),
        "task": _write(tmp_path / "task.json", TASK),
        "workflow": _write(tmp_path / "workflow.json", PLAN),
        "tmp": tmp_path,
    }


def _open(ws, capsys) -> dict:
    code = session_cli.main([
        "--state", ws["state"],
        "--task", ws["task"], "--workflow", ws["workflow"], "open",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0, payload
    return payload


def _record(ws, capsys, document) -> tuple[int, dict]:
    result = _write(ws["tmp"] / "result.json", document)
    code = session_cli.main(["--state", ws["state"], "--result", result, "record"])
    return code, json.loads(capsys.readouterr().out)


def test_open_reports_ready_and_the_stage_list(workspace, capsys):
    payload = _open(workspace, capsys)

    assert payload["detail"]["ready"] is True
    assert payload["detail"]["guidance"] == "asset-roundtrip"
    assert payload["detail"]["nodes"] == [_stage_path()]


def test_open_rejects_a_required_stage_without_both_checklists(workspace, capsys):
    workflow = json.loads(json.dumps(PLAN))
    workflow["root"]["children"][0]["stage"]["execution_checklist"] = []
    workspace["workflow"] = _write(workspace["tmp"] / "bad-workflow.json", workflow)

    code = session_cli.main([
        "--state", workspace["state"],
        "--task", workspace["task"], "--workflow", workspace["workflow"], "open",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    # Either layer may catch this and both are right to: the spec states "a
    # required STAGE freezes both checklists" as minItems, and the validator states
    # it as a rule. The spec runs first, so its spelling is what arrives.
    message = payload["errors"][0]
    assert "execution_checklist" in message or "execution checklist" in message, message


def test_a_proven_relation_completes_the_stage(workspace, capsys):
    _open(workspace, capsys)
    code, _ = _record(workspace, capsys, {
        "call_id": "v1",
        "status": "succeeded",
        "target": {"owner": "blender", "name": "read_scene"},
        "preserved_relations": ["asset_identity"],
    })
    assert code == 0

    code = session_cli.main(["--state", workspace["state"], "--stage", _stage_path(), "stage"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["detail"]["status"] == "succeeded"
    assert payload["detail"]["check_results"][0]["status"] == "pass"


def test_tool_success_without_relation_evidence_fails_the_stage(workspace, capsys):
    """The core promise: a succeeded call is not a completed Stage."""

    _open(workspace, capsys)
    _record(workspace, capsys, {
        "call_id": "v1",
        "status": "succeeded",
        "target": {"owner": "blender", "name": "read_scene"},
        "preserved_relations": [],
    })

    code = session_cli.main(["--state", workspace["state"], "--stage", _stage_path(), "stage"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    stage = payload["detail"]
    assert stage["status"] == "failed"
    assert stage["execution_results"][0]["status"] == "succeeded"
    assert stage["check_results"][0]["status"] == "fail"


def test_finish_aggregates_the_recorded_evidence(workspace, capsys):
    _open(workspace, capsys)
    _record(workspace, capsys, {
        "call_id": "v1",
        "status": "succeeded",
        "target": {"owner": "blender", "name": "read_scene"},
        "preserved_relations": ["asset_identity"],
    })
    session_cli.main(["--state", workspace["state"], "--stage", _stage_path(), "stage"])
    capsys.readouterr()

    code = session_cli.main(["--state", workspace["state"], "finish"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["detail"]["status"] == "succeeded"
    assert payload["detail"]["nodes_completed"] == _completed_paths()


def test_status_reports_remaining_stages_without_changing_state(workspace, capsys):
    _open(workspace, capsys)

    code = session_cli.main(["--state", workspace["state"], "status"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["detail"]["remaining_nodes"] == [_stage_path()]
    assert payload["detail"]["completed_nodes"] == []


def test_state_persists_across_invocations(workspace, capsys):
    _open(workspace, capsys)
    _record(workspace, capsys, {
        "call_id": "v1",
        "status": "succeeded",
        "target": {"owner": "blender", "name": "read_scene"},
        "preserved_relations": ["asset_identity"],
    })

    stored = json.loads(Path(workspace["state"]).read_text(encoding="utf-8"))

    assert stored["version"] == 1
    assert stored["workflow"]["guidance"] == "asset-roundtrip"
    assert [event["type"] for event in stored["events"]] == ["execution_result"]


def test_recording_a_call_the_plan_never_declared_is_rejected(workspace, capsys):
    _open(workspace, capsys)

    code = session_cli.main([
        "--state", workspace["state"], "--result",
        _write(workspace["tmp"] / "unknown.json", {
            "call_id": "not-in-workflow",
            "status": "succeeded",
        }),
        "record",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert "not declared in the Workflow" in payload["errors"][0]


def test_missing_state_file_is_reported_not_crashed(tmp_path, capsys):
    code = session_cli.main(["--state", str(tmp_path / "absent.json"), "status"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert "does not exist" in payload["errors"][0]


DEPENDENT_PLAN = {
    "guidance": "asset-roundtrip",
    "route": "asset_transfer",
    "workflow_id": "dep:workflow",
    "root": {
        "node_id": "work",
        "kind": "workflow",
        "purpose": "Two ordered stages",
        "children": [
            {
                "node_id": "stage.first",
                "kind": "stage",
                "purpose": "First",
                "stage": {
                    "stage_kind": "change",
                    "calls": [
                        {"call_id": "v1", "target": {"owner": "blender", "name": "read_scene"}}
                    ],
                    "execution_checklist": [{"item_id": "i1", "description": "run", "call_ids": ["v1"]}],
                    "acceptance_checklist": [
                        {
                            "check_id": "c1",
                            "description": "proven",
                            "operator": "truthy",
                            "source_call_id": "v1",
                            "actual_path": ["preserved_relations"],
                        }
                    ],
                },
            },
            {
                "node_id": "stage.second",
                "kind": "stage",
                "purpose": "Second",
                "depends_on": ["../stage.first"],
                "stage": {
                    "stage_kind": "change",
                    "calls": [
                        {"call_id": "v2", "target": {"owner": "blender", "name": "read_scene"}}
                    ],
                    "execution_checklist": [{"item_id": "i2", "description": "run", "call_ids": ["v2"]}],
                    "acceptance_checklist": [
                        {
                            "check_id": "c2",
                            "description": "proven",
                            "operator": "truthy",
                            "source_call_id": "v2",
                            "actual_path": ["preserved_relations"],
                        }
                    ],
                },
            },
        ],
    },
}


def _dependent_workspace(tmp_path: Path) -> dict:
    return {
        "state": str(tmp_path / "state.json"),
        "task": _write(tmp_path / "task.json", TASK),
        "workflow": _write(tmp_path / "workflow.json", DEPENDENT_PLAN),
        "tmp": tmp_path,
    }


def _dependent_workflow():
    return workflow_from_dict(DEPENDENT_PLAN)


def _call_result(call_id: str) -> dict:
    return {
        "call_id": call_id,
        "status": "succeeded",
        "target": {"owner": "blender", "name": "read_scene"},
        "preserved_relations": ["asset_identity"],
    }


def test_recording_a_call_before_its_stage_dependency_closes_is_rejected(tmp_path, capsys):
    ws = _dependent_workspace(tmp_path)
    _open(ws, capsys)

    code, payload = _record(ws, capsys, _call_result("v2"))

    assert code == 2
    assert "incomplete dependencies" in payload["errors"][0]


def test_ordered_replay_completes_every_dependent_stage(tmp_path, capsys):
    """Replay must follow submitted order, not a flat set of results."""

    ws = _dependent_workspace(tmp_path)
    _open(ws, capsys)
    workflow = _dependent_workflow()
    first, second = workflow.stage_paths

    assert _record(ws, capsys, _call_result("v1"))[0] == 0
    code = session_cli.main(["--state", ws["state"], "--stage", first, "stage"])
    assert code == 0, json.loads(capsys.readouterr().out)
    capsys.readouterr()

    assert _record(ws, capsys, _call_result("v2"))[0] == 0
    code = session_cli.main(["--state", ws["state"], "--stage", second, "stage"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["detail"]["status"] == "succeeded"

    code = session_cli.main(["--state", ws["state"], "finish"])
    finished = json.loads(capsys.readouterr().out)

    assert code == 0
    assert finished["detail"]["nodes_completed"] == [*workflow.composite_paths, first, second]


AMBIGUOUS_PLAN = {
    "guidance": "asset-roundtrip",
    "route": "asset_transfer",
    "workflow_id": "ambiguous:workflow",
    "root": {
        "node_id": "work",
        "kind": "workflow",
        "purpose": "Two subtrees that each declare the same call",
        "children": [
            {
                "node_id": side,
                "kind": "stage",
                "purpose": f"{side} read",
                "stage": {
                    "stage_kind": "change",
                    "calls": [
                        {"call_id": "shared", "target": {"owner": "blender", "name": "read_scene"}}
                    ],
                    "execution_checklist": [
                        {"item_id": f"{side}.ran", "description": "run", "call_ids": ["shared"]}
                    ],
                    "acceptance_checklist": [
                        {
                            "check_id": f"{side}.ok",
                            "description": "proven",
                            "operator": "tool_succeeded",
                            "source_call_id": "shared",
                            "call_ids": ["shared"],
                        }
                    ],
                },
            }
            for side in ("stage.left", "stage.right")
        ],
    },
}


def _ambiguous_workspace(tmp_path: Path) -> dict:
    return {
        "state": str(tmp_path / "state.json"),
        "task": _write(tmp_path / "task.json", TASK),
        "workflow": _write(tmp_path / "workflow.json", AMBIGUOUS_PLAN),
        "tmp": tmp_path,
    }


def test_recording_an_ambiguous_call_names_the_node_it_belongs_to(tmp_path, capsys):
    """A call id is scoped to its STAGE, so an ambiguous result must name the node.

    The replay that follows a `record` re-resolves the call, so a call whose node
    was not stored would be refused again on the next command. Closing the node
    afterwards proves the attribution survived the round trip.
    """

    ws = _ambiguous_workspace(tmp_path)
    _open(ws, capsys)
    first = workflow_from_dict(AMBIGUOUS_PLAN).stage_paths[0]

    code, payload = _record(ws, capsys, _call_result("shared"))
    assert code == 2
    assert "declared by more than one node" in payload["errors"][0]

    result = _write(tmp_path / "shared.json", _call_result("shared"))
    code = session_cli.main(
        ["--state", ws["state"], "--result", result, "--stage", first, "record"]
    )
    assert code == 0, json.loads(capsys.readouterr().out)
    capsys.readouterr()

    code = session_cli.main(["--state", ws["state"], "--stage", first, "stage"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["detail"]["status"] == "succeeded"


def test_two_nodes_may_each_record_a_call_with_the_same_id(tmp_path, capsys):
    """A call id is scoped to its STAGE: each subtree may declare and run its own.

    Two towers may each declare ``shared``. They are different calls, so recording
    the second is not a re-run of the first and must not be refused.
    """

    ws = _ambiguous_workspace(tmp_path)
    _open(ws, capsys)
    first, second = workflow_from_dict(AMBIGUOUS_PLAN).stage_paths
    result = _write(tmp_path / "shared.json", _call_result("shared"))

    for path in (first, second):
        code = session_cli.main(
            ["--state", ws["state"], "--result", result, "--stage", path, "record"]
        )
        assert code == 0, json.loads(capsys.readouterr().out)
        capsys.readouterr()
