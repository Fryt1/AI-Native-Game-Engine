"""Every invocation prints one envelope, whatever the input.

The contract in `docs/cli.md` is that each command prints one JSON object. A
`SkillIntegrityError` used to escape the error handler and print a traceback
instead, so a caller parsing stdout got nothing and could not tell a bug from bad
input.

These tests feed the CLI malformed, missing, and hostile inputs, and assert that
each one still produces a well-formed envelope with a diagnosable message.
"""

import json

import pytest

from ainative.cli import commands as session_cli
from ainative.cli.output import EXIT_UNUSABLE

ENVELOPE_KEYS = ["command", "ok", "verdict", "exit_code", "detail", "errors"]


def _write(path, data):
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


GOOD_STAGE = {
    "node_id": "s",
    "kind": "stage",
    "purpose": "p",
    "stage": {
        "stage_kind": "change",
        "calls": [{"call_id": "c1", "target": {"owner": "ue5", "name": "do"}}],
        "execution_checklist": [{"item_id": "i", "description": "d", "call_ids": ["c1"]}],
        "acceptance_checklist": [
            {"check_id": "k", "description": "d", "operator": "tool_succeeded",
             "source_call_id": "c1", "call_ids": ["c1"]}
        ],
    },
}


def _workflow(**overrides):
    doc = {
        "workflow_id": "p",
        "guidance": "host-operation",
        "revision": 1,
        "root": {"node_id": "w", "kind": "workflow", "purpose": "w",
                 "children": [GOOD_STAGE]},
    }
    doc.update(overrides)
    return doc


def _task(**overrides):
    doc = {
        "task_id": "p", "objective": "o", "guidance": "host-operation",
    }
    doc.update(overrides)
    return doc


@pytest.fixture
def paths(tmp_path):
    return {
        "task": _write(tmp_path / "task.json", _task()),
        "workflow": _write(tmp_path / "wf.json", _workflow()),
        "state": str(tmp_path / "state.json"),
        "tmp": tmp_path,
    }


def _open_with(capsys, paths, *, task=None, workflow=None):
    code = session_cli.main([
        "--state", paths["state"],
        "--task", task if task is not None else paths["task"],
        "--workflow", workflow if workflow is not None else paths["workflow"],
        "open",
    ])
    return code, json.loads(capsys.readouterr().out)


def test_an_unknown_guidance_name_reports_an_envelope(paths, capsys):
    """This exact case used to print a traceback."""

    bad = _write(paths["tmp"] / "bad-task.json", _task(guidance="no-such-document"))

    code, payload = _open_with(capsys, paths, task=bad)

    assert code == EXIT_UNUSABLE
    assert list(payload) == ENVELOPE_KEYS
    assert payload["command"] == "open"
    assert "named guidance does not exist" in payload["errors"][0]


@pytest.mark.parametrize(
    ("label", "task_doc", "workflow_doc"),
    [
        ("unknown guidance", _task(guidance="nope"), _workflow()),
        ("invalid workflow status", _task(), _workflow(status="NOT_A_STATUS")),
        ("task is a list", [1, 2, 3], _workflow()),
        ("task is empty", {}, _workflow()),
        ("workflow is a list", _task(), [1, 2]),
        ("workflow is empty", _task(), {}),
        ("root is a string", _task(), _workflow(root="nope")),
        ("workflow is not JSON", _task(), "{not json"),
        (
            "stage depends on itself",
            _task(),
            _workflow(root={"node_id": "w", "kind": "workflow", "purpose": "w",
                            "children": [{**GOOD_STAGE, "depends_on": ["s"]}]}),
        ),
    ],
)
def test_no_input_escapes_as_a_traceback(paths, capsys, label, task_doc, workflow_doc):
    task = _write(paths["tmp"] / f"t-{abs(hash(label))}.json", task_doc)
    workflow = _write(paths["tmp"] / f"w-{abs(hash(label))}.json", workflow_doc)

    code, payload = _open_with(capsys, paths, task=task, workflow=workflow)

    assert list(payload) == ENVELOPE_KEYS, label
    assert payload["exit_code"] == code, label
    assert payload["ok"] is (code == 0), label
    if code != 0:
        assert payload["errors"], f"{label}: a failure must say why"


def test_an_unexpected_exception_is_reported_not_raised(paths, capsys, monkeypatch):
    """A bug must still honour the output contract, and stay diagnosable."""

    def explode(_args):
        raise RuntimeError("something nobody anticipated")

    monkeypatch.setitem(session_cli.COMMANDS, "status", explode)
    _open_with(capsys, paths)

    code = session_cli.main(["--state", paths["state"], "status"])
    payload = json.loads(capsys.readouterr().out)

    assert code == EXIT_UNUSABLE
    assert list(payload) == ENVELOPE_KEYS
    assert "unexpected RuntimeError" in payload["errors"][0]
    assert "something nobody anticipated" in payload["errors"][0]


def test_the_error_message_no_longer_says_plan(paths, capsys):
    """The artifact is a Workflow; its errors must not call it a plan."""

    bad = _write(paths["tmp"] / "list.json", [1, 2])

    _, payload = _open_with(capsys, paths, workflow=bad)

    assert "plan" not in payload["errors"][0]
    assert payload["errors"][0].startswith("workflow")
