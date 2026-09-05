# Workflow Policy: Asset Edit

## Route Family

```text
asset_transfer
```

This policy describes an asset-edit lifecycle. A concrete Workflow such as
`asset-roundtrip.md` supplies host-pair constraints; the Agent writes the actual
plan.

## Purpose

Change an existing asset while making the edit representation, preservation
policy, publication, and validation explicit.

## Recommended macro flow

```text
prepare asset context when needed
    ↓
make the asset available to the edit host when needed
    ↓
perform the requested edit
    ↓
return or publish the result when requested
    ↓
validate the declared output and preserved relations
```

These are phase goals, not fixed Tool Calls. A Step may contain multiple Stages,
and optional phases may be omitted when their contract is already satisfied.

## Stage contract requirements

Every Stage selected by the Agent should declare:

```text
local purpose
inputs
outputs
gate
selected Tool Calls
validation
evidence
failure / recovery
```

The Stage selects Tools from a Toolset Registry; it does not invent raw host API
calls.

## Completion

The Agent completes the Workflow only after every required validation Stage in
its plan passes. Tool and Stage results remain available for the next Stage or
for re-planning.

## Failure / recovery

Preserve all produced artifacts and evidence. Resume the failed selected Tool
when the plan remains valid. Supersede and replace the plan when the Route,
branch, or Stage contract is wrong.

## Dynamic Stage checklist rule

For each selected Stage, the Agent loads the relevant `knowledge/stage-kinds`,
`knowledge/objects`, and `knowledge/operations` documents, then freezes an
execution checklist and an acceptance checklist in the WorkflowPlan. Checklist
knowledge does not name Tools; the final plan stores exact Tool Calls from the
live Registry.

A Tool returning `succeeded` is call-level evidence only. The Stage completes
through evidence-backed `ExecutionItemResult` and `CheckResult` aggregation.
