"""Analyze one Agent-chain trace file (JSONL) produced by AgentTrace.

Usage:
    python scripts/trace/analyze_trace.py <run-id-or-path> [--json]

The analyzer is read-only. It prints a chronological digest of every recorded
event and flags structural issues that indicate context-engineering breakage:
missing task/plan/result events, call results without matching plan calls,
gate blocking, and Stage/Task outcomes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(r"D:\work\AI-Native-Game-Engine")
TRACE_DIR = PROJECT_ROOT / "artifacts" / "traces"


def load_events(source: str) -> tuple[Path, list[dict]]:
    path = Path(source)
    if not path.is_file():
        path = TRACE_DIR / source
        if not path.exists():
            path = TRACE_DIR / f"{source}.jsonl"
    if not path.is_file():
        raise SystemExit(f"trace not found: {source} (tried {path})")
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return path, events


def summarize(events: list[dict]) -> dict:
    kinds = [event.get("event", "?") for event in events]
    counts = Counter(kinds)
    call_inputs = [e for e in events if e.get("event") == "call.input"]
    call_results = [e for e in events if e.get("event") == "call.result"]
    stage_results = [e for e in events if e.get("event") == "stage.result"]
    task_results = [e for e in events if e.get("event") == "task.result"]
    blocked_gates = [e for e in events if e.get("event") == "gate.result" and e.get("data", {}).get("ready") is False]
    tool_issue_events = [e for e in events if e.get("event") == "plan.tool_issues" and e.get("data", {}).get("issues")]
    failed_calls = [e for e in call_results if e.get("data", {}).get("result", {}).get("status") not in ("succeeded", "degraded")]
    return {
        "event_counts": dict(counts),
        "calls_planned": len(call_inputs),
        "calls_resulted": len(call_results),
        "stages_resulted": len(stage_results),
        "task_results": len(task_results),
        "blocked_gates": len(blocked_gates),
        "tool_issue_events": len(tool_issue_events),
        "failed_or_blocked_calls": len(failed_calls),
    }


def detect_issues(events: list[dict]) -> list[str]:
    issues: list[str] = []
    events_by_id: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        run_id = event.get("run_id")
        if run_id:
            events_by_id[run_id].append(event)
    for run_id, run_events in events_by_id.items():
        names = [e.get("event") for e in run_events]
        if "task.input" not in names:
            issues.append(f"[{run_id}] missing task.input")
        if "skill.selected" not in names:
            issues.append(f"[{run_id}] missing skill.selected")
        if "plan.input" not in names:
            issues.append(f"[{run_id}] missing plan.input")
        if "task.result" not in names:
            issues.append(f"[{run_id}] missing task.result (workflow may still be open)")
        for gate in [e for e in run_events if e.get("event") == "gate.result" and e["data"].get("ready") is False]:
            issues.append(f"[{run_id}] entry gate blocked: {gate['data'].get('blocked_reasons')}")
        tool_issue_events = [e for e in run_events if e.get("event") == "plan.tool_issues" and e["data"].get("issues")]
        if tool_issue_events:
            count = sum(len(e["data"]["issues"]) for e in tool_issue_events)
            issues.append(f"[{run_id}] plan tool issues: {count}")
        call_inputs = [e for e in run_events if e.get("event") == "call.input"]
        call_results = [e for e in run_events if e.get("event") == "call.result"]
        if len(call_inputs) != len(call_results):
            issues.append(f"[{run_id}] call inputs/results mismatch: {len(call_inputs)} inputs vs {len(call_results)} results")
        stage_results = [e for e in run_events if e.get("event") == "stage.result"]
        stage_statuses = [e["data"]["stage"].get("status") for e in stage_results]
        bad = [s for s in stage_statuses if s not in ("succeeded", "degraded")]
        if bad:
            issues.append(f"[{run_id}] non-success Stage results: {bad}")
        task_results = [e for e in run_events if e.get("event") == "task.result"]
        for tr in task_results:
            status = tr["data"]["result"].get("status")
            if status not in ("succeeded", "degraded"):
                issues.append(f"[{run_id}] final Task status: {status}")
    return issues


def print_report(path: Path, events: list[dict], as_json: bool) -> None:
    summary = summarize(events)
    issues = detect_issues(events)
    if as_json:
        payload = {
            "trace_path": str(path),
            "events": len(events),
            "summary": summary,
            "issues": issues,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"Trace: {path}")
    print(f"Events: {len(events)}")
    print("\nSummary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print("\nChronology:")
    for event in events:
        stamp = event.get("timestamp", "")[11:23]
        name = event.get("event", "?")
        data = event.get("data", {})
        if name == "task.input":
            line = f"task={data.get('task', {}).get('task_id', '?')} route={data.get('task', {}).get('route', '?')} objective={str(data.get('task', {}).get('objective', ''))[:80]!r}"
        elif name == "skill.selected":
            line = f"skill={data.get('skill_id')} workflow={data.get('selection', {}).get('workflow_id')} profile={data.get('selection', {}).get('profile')}"
        elif name == "plan.input":
            line = f"plan={data.get('plan', {}).get('plan_id')} revision={data.get('plan', {}).get('revision')} route={data.get('plan', {}).get('route')}"
        elif name == "call.input":
            call = data.get("call", {})
            line = f"{call.get('kind')} {call.get('call_id')} -> {call.get('tool_id') or call.get('server_id') + '.' + call.get('tool_name', '')} args={json.dumps(call.get('arguments', {}), ensure_ascii=False)[:200]}"
        elif name == "call.result":
            result = data.get("result", {})
            line = f"{result.get('call_id')} status={result.get('status')} outputs={json.dumps(result.get('outputs', {}), ensure_ascii=False)[:200]}"
        elif name == "stage.result":
            stage = data.get("stage", {})
            line = f"{stage.get('stage_id')} status={stage.get('status')} calls={stage.get('call_ids')} exec_summary={stage.get('execution_summary')} acc_summary={stage.get('acceptance_summary')}"
        elif name == "task.result":
            result = data.get("result", {})
            line = f"status={result.get('status')} stages_completed={result.get('stages_completed')}"
        elif name == "gate.result":
            line = f"ready={data.get('ready')} blocked={data.get('blocked_reasons')}"
        else:
            line = json.dumps(data, ensure_ascii=False)[:200]
        print(f"  {stamp} {name:18s} {line}")
    print("\nIssues:")
    if issues:
        for issue in issues:
            print(f"  ! {issue}")
    else:
        print("  none")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze an AgentTrace JSONL file")
    parser.add_argument("source", help="trace run id or path to .jsonl")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    path, events = load_events(args.source)
    print_report(path, events, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
