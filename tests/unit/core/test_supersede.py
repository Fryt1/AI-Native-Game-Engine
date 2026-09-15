"""Replacing a Workflow revision, and what happens to work already done.

Two facts drive this behaviour:

    A Stage carries over only when its *definition* is unchanged. Same stage_id
    is not enough: if the goal, the checklist, or the calls changed, the earlier
    verdict says nothing about the new Stage.

    A Stage that recorded a call has already run against a live host. Python
    cannot see or undo that, so re-running it is refused until the Agent says it
    means to.

Both are verified end to end through the CLI, because the interaction between
carry-over and replay is where the earlier version of this went wrong.
"""

import json
import pathlib

import pytest

from ainative.cli import commands as session_cli
from ainative.cli.output import EXIT_BLOCKING, EXIT_OK, EXIT_UNUSABLE
from ainative.model.workflow import StageRequest, Workflow

ENVELOPE_KEYS = ["command", "ok", "verdict", "exit_code", "detail", "errors"]


# --- the fingerprint -----------------------------------------------------------


def _stage(**overrides):
    base = {
        "stage_id": "stage.a",
        "purpose": "Do the thing",
        "stage_kind": "change",
        "calls": [{"call_id": "c1", "target": {"owner": "ue5", "name": "do_thing"}}],
        "execution_checklist": [{"item_id": "i1", "description": "ran", "call_ids": ["c1"]}],
        "acceptance_checklist": [
            {"check_id": "k1", "description": "ok", "operator": "tool_succeeded", "call_ids": ["c1"]}
        ],
    }
    base.update(overrides)
    return base


def _stage_with_spare_call(**overrides):
    """A Stage declaring a second, not-yet-recorded call.

    Used to test what happens when a call is reported for a Stage that is already
    closed: the call must be declared, or the earlier 'undeclared call' check
    fires and hides the guard under test.
    """

    return _stage(
        calls=[
            {"call_id": "c1", "target": {"owner": "ue5", "name": "do_thing"}},
            {"call_id": "c2", "target": {"owner": "ue5", "name": "do_thing_again"}},
        ],
        execution_checklist=[
            {"item_id": "i1", "description": "ran", "call_ids": ["c1", "c2"]}
        ],
        acceptance_checklist=[
            {"check_id": "k1", "description": "ok", "operator": "tool_succeeded",
             "call_ids": ["c1", "c2"]}
        ],
        **overrides,
    )


def _workflow(stages, revision=1, supersedes=None):
    doc = {
        "workflow_id": "t:workflow",
        "guidance": "host-operation",
        "route": "host_operation",
        "revision": revision,
        "steps": [{"step_id": "work", "purpose": "work", "stages": stages}],
    }
    if supersedes:
        doc["supersedes_workflow_id"] = supersedes
    return doc


def _fingerprint(stage_dict):
    from ainative.reading.deserialize import workflow_from_dict

    workflow = workflow_from_dict(_workflow([stage_dict]))
    return workflow.stage_requests[0].fingerprint


def test_an_identical_stage_has_the_same_fingerprint():
    assert _fingerprint(_stage()) == _fingerprint(_stage())


def test_stage_id_is_not_part_of_the_fingerprint():
    """Renaming a Stage does not change what it does, so it is still the same work."""

    assert _fingerprint(_stage()) == _fingerprint(_stage(stage_id="stage.renamed"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("purpose", "A different goal"),
        ("stage_kind", "investigation"),
        ("calls", [{"call_id": "c1", "target": {"owner": "ue5", "name": "do_other"}}]),
        ("execution_checklist", [{"item_id": "i1", "description": "other", "call_ids": ["c1"]}]),
        (
            "acceptance_checklist",
            [{"check_id": "k1", "description": "ok", "operator": "truthy",
              "source_call_id": "c1", "actual_path": ["x"], "call_ids": ["c1"]}],
        ),
    ],
)
def test_changing_any_decision_changes_the_fingerprint(field, value):
    """Every field that decides the outcome must be part of the identity."""

    assert _fingerprint(_stage()) != _fingerprint(_stage(**{field: value}))


# --- end to end ----------------------------------------------------------------


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


@pytest.fixture
def workspace(tmp_path, capsys):
    state = str(tmp_path / "state.json")
    task = _write(tmp_path / "task.json", {
        "task_id": "t", "objective": "o", "route": "host_operation", "guidance": "host-operation",
    })

    def open_with(stages, revision=1, supersedes=None):
        workflow = _write(tmp_path / f"wf{revision}.json", _workflow(stages, revision, supersedes))
        code = session_cli.main(["--state", state, "--task", task, "--workflow", workflow, "open"])
        return code, json.loads(capsys.readouterr().out)

    def supersede_with(stages, revision, supersedes, reason="changed"):
        workflow = _write(tmp_path / f"wf{revision}.json", _workflow(stages, revision, supersedes))
        code = session_cli.main(
            ["--state", state, "--workflow", workflow, "--reason", reason, "supersede"]
        )
        return code, json.loads(capsys.readouterr().out)

    def record(call_id, tool, *extra):
        result = _write(tmp_path / f"{call_id}.json", {
            "call_id": call_id, "status": "succeeded",
            "target": {"owner": "ue5", "name": tool},
        })
        code = session_cli.main(["--state", state, "--result", result, *extra, "record"])
        return code, json.loads(capsys.readouterr().out)

    def stage(stage_id, *extra):
        code = session_cli.main(["--state", state, "--stage", stage_id, *extra, "stage"])
        return code, json.loads(capsys.readouterr().out)

    return {
        "state": state, "capsys": capsys, "open": open_with,
        "supersede": supersede_with, "record": record, "stage": stage,
    }


STAGES = [
    _stage(),
    _stage(stage_id="stage.b", calls=[{"call_id": "b1", "target": {"owner": "ue5", "name": "do_b"}}],
           execution_checklist=[{"item_id": "ib", "description": "ran", "call_ids": ["b1"]}],
           acceptance_checklist=[{"check_id": "kb", "description": "ok",
                                  "operator": "tool_succeeded", "call_ids": ["b1"]}]),
]


def test_adding_a_stage_keeps_the_finished_one_closed(workspace):
    """The common case: the Agent discovers one more step is needed."""

    workspace["open"](STAGES, revision=1)
    workspace["record"]("c1", "do_thing")
    workspace["stage"]("stage.a")

    code, payload = workspace["supersede"](
        [*STAGES, _stage(stage_id="stage.c",
                         calls=[{"call_id": "z1", "target": {"owner": "ue5", "name": "do_c"}}],
                         execution_checklist=[{"item_id": "iz", "description": "ran", "call_ids": ["z1"]}],
                         acceptance_checklist=[{"check_id": "kz", "description": "ok",
                                                "operator": "tool_succeeded", "call_ids": ["z1"]}])],
        revision=2, supersedes="t:workflow:r1",
    )

    assert code == EXIT_OK
    assert payload["detail"]["carried_over"] == ["stage.a", "stage.b"]
    assert payload["detail"]["invalidated"] == ["stage.c"]
    assert payload["detail"]["side_effects_at_risk"] == []

    # The finished Stage carried its evidence over, so asking again is idempotent.
    code, status = workspace["stage"]("stage.a")
    assert code == EXIT_OK
    assert status["verdict"] == "succeeded"

    # The new Stage has run nothing, so it cannot close yet.
    code, status = workspace["stage"]("stage.c")
    assert code == EXIT_BLOCKING
    assert status["verdict"] == "blocked"


def test_a_half_done_stage_keeps_its_recorded_call(workspace):
    """A Stage whose calls ran but which was never closed can still be closed."""

    workspace["open"](STAGES, revision=1)
    workspace["record"]("b1", "do_b")

    workspace["supersede"](STAGES, revision=2, supersedes="t:workflow:r1")

    code, payload = workspace["stage"]("stage.b")
    assert code == EXIT_OK
    assert payload["verdict"] == "succeeded"


def test_changing_a_checklist_invalidates_that_stage(workspace):
    workspace["open"](STAGES, revision=1)
    workspace["record"]("b1", "do_b")

    tightened = _stage(
        stage_id="stage.b",
        calls=[{"call_id": "b1", "target": {"owner": "ue5", "name": "do_b"}}],
        execution_checklist=[{"item_id": "ib", "description": "ran", "call_ids": ["b1"]}],
        acceptance_checklist=[
            {"check_id": "kb", "description": "ok", "operator": "tool_succeeded", "call_ids": ["b1"]},
            {"check_id": "extra", "description": "new proof", "operator": "truthy",
             "source_call_id": "b1", "actual_path": ["preserved_relations"], "call_ids": ["b1"]},
        ],
    )
    _, payload = workspace["supersede"]([tightened], revision=2, supersedes="t:workflow:r1")

    assert payload["detail"]["carried_over"] == []
    assert "stage.b" in payload["detail"]["invalidated"]
    assert payload["detail"]["side_effects_at_risk"] == ["stage.b"]


def test_re_reporting_a_call_that_already_ran_is_refused(workspace):
    """The reachable hazard: a replacement revision makes an old call runnable again."""

    workspace["open"](STAGES, revision=1)
    workspace["record"]("c1", "do_thing")

    code, payload = workspace["record"]("c1", "do_thing")

    assert code == EXIT_UNUSABLE
    assert list(payload) == ENVELOPE_KEYS
    assert "has already run against a live host" in payload["errors"][0]


def test_the_refusal_can_be_overridden_explicitly(workspace):
    workspace["open"](STAGES, revision=1)
    workspace["record"]("c1", "do_thing")

    code, payload = workspace["record"]("c1", "do_thing", "--confirm-side-effects")

    # The repeat guard is satisfied, so the ordinary duplicate-call rule reports.
    assert code == EXIT_UNUSABLE
    assert "already been recorded" in payload["errors"][0]


def test_a_replaced_stage_refuses_its_call_again(workspace, tmp_path, capsys):
    """Even after the revision that ran the call is archived, the call is remembered."""

    workspace["open"](STAGES, revision=1)
    workspace["record"]("c1", "do_thing")
    workspace["stage"]("stage.a")

    # Change the goal, so the Stage is invalidated rather than carried over.
    changed = _stage(purpose="A different goal")
    code, payload = workspace["supersede"]([changed], revision=2, supersedes="t:workflow:r1")

    assert payload["detail"]["invalidated"] == ["stage.a"]
    assert payload["detail"]["side_effects_at_risk"] == ["stage.a"]

    code, payload = workspace["record"]("c1", "do_thing")

    assert code == EXIT_UNUSABLE
    assert "has already run against a live host" in payload["errors"][0]


def test_evaluating_a_stage_after_its_own_calls_is_not_refused(workspace):
    """The normal path must never trip the guard."""

    workspace["open"](STAGES, revision=1)
    workspace["record"]("c1", "do_thing")

    code, payload = workspace["stage"]("stage.a")

    assert code == EXIT_OK
    assert payload["verdict"] == "succeeded"
    assert payload["detail"]["side_effects_recorded"] is True


def test_a_replacement_must_name_the_revision_it_replaces(workspace):
    """With progress recorded, an unnamed replacement would silently discard it."""

    workspace["open"](STAGES, revision=1)
    workspace["record"]("c1", "do_thing")

    code, payload = workspace["supersede"](STAGES, revision=2, supersedes=None)

    assert code == EXIT_UNUSABLE
    assert "must name the revision it replaces" in payload["errors"][0]


def test_open_refuses_to_overwrite_a_state_with_progress(workspace, tmp_path):
    """Reopening would drop evidence, so the Agent must supersede instead."""

    workspace["open"](STAGES, revision=1)
    workspace["record"]("c1", "do_thing")

    task = str(tmp_path / "task.json")
    workflow = str(tmp_path / "wf1.json")
    code = session_cli.main(["--state", workspace["state"], "--task", task,
                             "--workflow", workflow, "open"])
    payload = json.loads(workspace["capsys"].readouterr().out)

    assert code == EXIT_UNUSABLE
    assert "already has recorded progress" in payload["errors"][0]
    assert "supersede" in payload["errors"][0]


def test_the_archived_revision_keeps_its_evidence(workspace):
    """The audit trail must survive: what was attempted, and why it was dropped."""

    workspace["open"](STAGES, revision=1)
    workspace["record"]("b1", "do_b")

    tightened = _stage(
        stage_id="stage.b",
        calls=[{"call_id": "b1", "target": {"owner": "ue5", "name": "do_b"}}],
        execution_checklist=[{"item_id": "ib", "description": "changed", "call_ids": ["b1"]}],
        acceptance_checklist=[
            {"check_id": "kb", "description": "ok", "operator": "tool_succeeded", "call_ids": ["b1"]}],
    )
    workspace["supersede"]([tightened], revision=2, supersedes="t:workflow:r1", reason="changed ib")

    stored = json.loads(pathlib.Path(workspace["state"]).read_text(encoding="utf-8"))

    assert len(stored["revisions"]) == 1
    archived = stored["revisions"][0]
    assert archived["revision_id"] == "t:workflow:r1"
    assert archived["reason"] == "changed ib"
    assert len(archived["events"]) == 1
    assert archived["side_effect_stages"] == ["stage.b"]


def test_a_workflow_with_no_stages_round_trips():
    """The model accepts an empty Workflow; the fingerprint logic must not assume otherwise."""

    workflow = Workflow(guidance="g", route="host_operation", steps=())
    assert workflow.stage_requests == ()
    assert isinstance(StageRequest(stage_id="s", purpose="p"), StageRequest)
