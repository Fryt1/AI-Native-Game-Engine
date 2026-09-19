# Call, Checklist, and Result Contract

This is the other half of `workflow.schema.json`. That file defines the Workflow a
document must be; this one defines what the Agent submits against it. A Workflow and
its results are one contract, so they live side by side.

Result documents have no JSON Schema of their own -- the spec describes the Workflow,
not the results reported against it. This file is therefore the only place the
submitted shapes are written down, and the sections below are normative for the
values `record`, `item`, and `check` accept.

## No registry, no binding

There is no Toolset Registry, no execution binding, and no provider list. A Workflow
declares its calls directly, and the Agent's own MCP client resolves and runs
them. This repository validates the Workflow's structure and evaluates evidence; it
executes nothing.

## Call and Call Target

A call names *what the Agent will invoke*: a tool on a host's own MCP server,
invoked by the Agent's own MCP client.

A call is the Agent's exact selection:

```text
call_id
target
    owner       MCP server name
    name        tool name on that server
arguments
depends_on
```

The Agent, not this
repository, resolves the target. An MCP call such as

```json
{"call_id": "m1", "target": {"owner": "ue5", "name": "set_actor_transform"}}
```

is a normal entry in the Workflow's call graph: it participates in dependency
ordering and can carry a `tool_succeeded` acceptance check.

## Stage checklists

```text
execution checklist
    what must be handled to avoid omission

acceptance checklist
    what must be proven to complete the Stage
```

Checklist composition does not bind Tools. The final Workflow references the
exact calls the Agent selected.

## ExecutionResult — what `record` submits

An ExecutionResult records call-level facts:

```text
call_id
status
target
outputs
artifacts
warnings
errors
resume_pointer
preserved_relations
lost_relations
```

A submitted result must match its declared call: the `call_id` must be declared in
the Workflow, and the `target` must agree with that declaration.

Call `succeeded` means the invocation completed without a blocking call-level
error. It does not automatically mean a semantic acceptance item passed.

## ExecutionItemResult and CheckResult — what `item` and `check` submit

`item` submits an `item_id`; `check` submits a `check_id`. Both use:

```text
pass
warn
fail
unknown
needs_human
```

A pass/warn with `evidence_required: true` needs at least one evidence reference.
That reference travels in the SUBMITTED result, in a field called `evidence_refs`:

```json
{"item_id": "reviewed", "status": "pass", "evidence_refs": ["note:review-2024-01"]}
{"check_id": "signed",  "status": "pass", "evidence_refs": ["note:signoff-2024-01"]}
```

It is a non-empty list of strings. The engine does not parse them or check that
what they name exists -- they record what you looked at, and nothing else. Omit
them and the item or check is downgraded to `unknown`, which blocks the node; note
that the submission itself still reports success, so the failure surfaces on the
next command rather than this one. A result submitted with `record` does not need
them: the engine builds `execution-result:<call_id>` itself.

`item` and `check` accept a bare id only when exactly one node declares it; pass
`--stage` to name the node when it is ambiguous.

Simple deterministic checks support:

```text
tool_succeeded
exists
truthy
equals
set_equals
count_equals
within_tolerance
```

`manual` means an explicit CheckResult must be recorded. Reserve it for genuine
human judgment; a fact an MCP read-back can answer should be checked
deterministically against that call's evidence.

## StageResult

StageResult contains:

```text
ExecutionResult[]
ExecutionItemResult[]
CheckResult[]
execution_summary
acceptance_summary
status
artifacts / warnings / errors / resume_pointer
```

Its status is deterministically aggregated. The Agent decides what to do next,
but cannot override a required `fail`, `unknown`, or `needs_human` without new
evidence or an explicit human decision.
