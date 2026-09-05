import json
from argparse import Namespace
from pathlib import Path

from ainative.cli import runner
from ainative.orchestration.contracts import TaskResult, TaskStatus


class FakeRuntime:
    def resolve_tool(self, call):
        return object()


def test_cli_emits_structured_blocked_result_for_invalid_json_args(capsys):
    args = Namespace(
        config=None,
        task=None,
        toolset="blender.editor",
        tool=None,
        operation="inspect",
        args="{",
        call_id="bad-json",
        usage="execute",
    )

    exit_code = runner.run_tool_call(args)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["status"] == "blocked"
    assert payload["call_id"] == "bad-json"
    assert payload["errors"]


def test_cli_derives_transfer_backend_context_from_task(tmp_path: Path, monkeypatch, capsys):
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "task_id": "direct-cli",
                "objective": "direct transfer",
                "route": "asset_transfer",
                "preferred_backend": "direct",
                "source_context": {"app": "ue5"},
                "target_context": {"app": "ue5"},
                "metadata": {"export_file": str(tmp_path / "asset.glb")},
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    monkeypatch.setattr(runner, "build_runtime", lambda config: FakeRuntime())
    monkeypatch.setattr(
        runner,
        "execute_resolved",
        lambda runtime, call, resolved, ctx: (
            captured.update({"backend": ctx.plan_transfer_backend, "host": ctx.plan_host_app})
            or TaskResult(status=TaskStatus.SUCCEEDED, route="asset_transfer")
        ),
    )

    args = Namespace(
        config=None,
        task=str(task_path),
        toolset="transfer.direct",
        tool="transfer.direct.transfer_to_edit_host",
        operation=None,
        args="{}",
        call_id="direct-cli-call",
        usage="execute",
    )

    assert runner.run_tool_call(args) == 0
    json.loads(capsys.readouterr().out)
    assert captured == {"backend": "direct", "host": "blender"}
