"""End-to-end test of the Agent acceptance loop through the session CLI."""

import json
from pathlib import Path

import pytest

from ainative.cli import commands as session_cli

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
    "steps": [
        {
            "step_id": "validate",
            "purpose": "Validate",
            "stages": [
                {
                    "stage_id": "stage.validate_asset",
                    "purpose": "Validate result",
                    "operation": "validate",
                    "stage_kind": "change",
                    "calls": [
                        {
                            "call_id": "v1",
                            "kind": "mcp",
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
                }
            ],
        }
    ],
}


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

    assert payload["ready"] is True
    assert payload["guidance"] == "asset-roundtrip"
    assert payload["stages"] == ["stage.validate_asset"]


def test_open_rejects_a_required_stage_without_both_checklists(workspace, capsys):
    workflow = json.loads(json.dumps(PLAN))
    workflow["steps"][0]["stages"][0]["execution_checklist"] = []
    workspace["workflow"] = _write(workspace["tmp"] / "bad-workflow.json", workflow)

    code = session_cli.main([
        "--state", workspace["state"],
        "--task", workspace["task"], "--workflow", workspace["workflow"], "open",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert "execution checklist" in payload["errors"][0]


def test_a_proven_relation_completes_the_stage(workspace, capsys):
    _open(workspace, capsys)
    code, _ = _record(workspace, capsys, {
        "call_id": "v1",
        "kind": "mcp",
        "status": "succeeded",
        "target": {"owner": "blender", "name": "read_scene"},
        "preserved_relations": ["asset_identity"],
    })
    assert code == 0

    code = session_cli.main(["--state", workspace["state"], "--stage", "stage.validate_asset", "stage"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["stage_result"]["status"] == "succeeded"
    assert payload["stage_result"]["check_results"][0]["status"] == "pass"


def test_tool_success_without_relation_evidence_fails_the_stage(workspace, capsys):
    """The core promise: a succeeded call is not a completed Stage."""

    _open(workspace, capsys)
    _record(workspace, capsys, {
        "call_id": "v1",
        "kind": "mcp",
        "status": "succeeded",
        "target": {"owner": "blender", "name": "read_scene"},
        "preserved_relations": [],
    })

    code = session_cli.main(["--state", workspace["state"], "--stage", "stage.validate_asset", "stage"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    stage = payload["stage_result"]
    assert stage["status"] == "failed"
    assert stage["execution_results"][0]["status"] == "succeeded"
    assert stage["check_results"][0]["status"] == "fail"


def test_finish_aggregates_the_recorded_evidence(workspace, capsys):
    _open(workspace, capsys)
    _record(workspace, capsys, {
        "call_id": "v1",
        "kind": "mcp",
        "status": "succeeded",
        "target": {"owner": "blender", "name": "read_scene"},
        "preserved_relations": ["asset_identity"],
    })
    session_cli.main(["--state", workspace["state"], "--stage", "stage.validate_asset", "stage"])
    capsys.readouterr()

    code = session_cli.main(["--state", workspace["state"], "finish"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["task_result"]["status"] == "succeeded"
    assert payload["task_result"]["stages_completed"] == ["stage.validate_asset"]


def test_status_reports_remaining_stages_without_changing_state(workspace, capsys):
    _open(workspace, capsys)

    code = session_cli.main(["--state", workspace["state"], "status"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["remaining_stages"] == ["stage.validate_asset"]
    assert payload["completed_stages"] == []


def test_state_persists_across_invocations(workspace, capsys):
    _open(workspace, capsys)
    _record(workspace, capsys, {
        "call_id": "v1",
        "kind": "mcp",
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
            "kind": "mcp",
            "status": "succeeded",
        }),
        "record",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert "undeclared call" in payload["errors"][0]


def test_missing_state_file_is_reported_not_crashed(tmp_path, capsys):
    code = session_cli.main(["--state", str(tmp_path / "absent.json"), "status"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert "does not exist" in payload["errors"][0]


DEPENDENT_PLAN = {
    "guidance": "asset-roundtrip",
    "route": "asset_transfer",
    "workflow_id": "dep:workflow",
    "steps": [
        {
            "step_id": "work",
            "purpose": "Two ordered stages",
            "stages": [
                {
                    "stage_id": "stage.first",
                    "purpose": "First",
                    "operation": "validate",
                    "stage_kind": "change",
                    "calls": [
                        {"call_id": "v1", "kind": "mcp", "target": {"owner": "blender", "name": "read_scene"}}
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
                {
                    "stage_id": "stage.second",
                    "purpose": "Second",
                    "operation": "validate",
                    "stage_kind": "change",
                    "depends_on": ["stage.first"],
                    "calls": [
                        {"call_id": "v2", "kind": "mcp", "target": {"owner": "blender", "name": "read_scene"}}
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
            ],
        }
    ],
}


def _dependent_workspace(tmp_path: Path) -> dict:
    return {
        "state": str(tmp_path / "state.json"),
        "task": _write(tmp_path / "task.json", TASK),
        "workflow": _write(tmp_path / "workflow.json", DEPENDENT_PLAN),
        "tmp": tmp_path,
    }


def _call_result(call_id: str) -> dict:
    return {
        "call_id": call_id,
        "kind": "mcp",
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

    assert _record(ws, capsys, _call_result("v1"))[0] == 0
    code = session_cli.main(["--state", ws["state"], "--stage", "stage.first", "stage"])
    assert code == 0, json.loads(capsys.readouterr().out)
    capsys.readouterr()

    assert _record(ws, capsys, _call_result("v2"))[0] == 0
    code = session_cli.main(["--state", ws["state"], "--stage", "stage.second", "stage"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["stage_result"]["status"] == "succeeded"

    code = session_cli.main(["--state", ws["state"], "finish"])
    finished = json.loads(capsys.readouterr().out)

    assert code == 0
    assert finished["task_result"]["stages_completed"] == ["stage.first", "stage.second"]
