# Workflow Guidance: UE5–Blender Asset Roundtrip

## Purpose

Move an existing asset between a source host, an edit host, and a target host
when the task requires a cross-host edit or round-trip. Validate only the
relations promised by the Task Contract.

## Inputs

```text
source asset reference
source / edit / target host roles
requested modification
preserved relations
acceptable loss
return / reimport requirement
publication policy
```

## Output Contract

```text
source artifact
edit artifact
modified artifact
transfer evidence
import / reimport evidence
validation and loss report
StageResults
resume pointer on failure
```

## Recommended lifecycle

This is a macro lifecycle, not a fixed list of five Steps:

```text
identify source, edit, and target roles
    ↓
confirm each host's MCP server is reachable
    ↓
make the asset available in the edit host
    ↓
perform the edit
    ↓
return or publish the result when requested
    ↓
validate declared identity, relations, loss, and target evidence
```

The Agent may combine local goals into a Stage or split them into multiple
Stages. Any state-changing action must be an explicit call.

## Transfer path

Both hosts are reached through their own MCP servers. Moving an asset across the
host boundary means calling the source host's export and the target host's
import; the file that passes between them is the Agent's own file operation.

```text
export from the source host   → source host MCP call
pass the artifact between hosts → the Agent's file operation
import into the target host   → target host MCP call
```

This repository provides no transfer Tool. It cannot promise host asset identity
restoration or reimport semantics, because that depends entirely on the export and
import calls the Agent selects. A relation the Workflow promises must be obtained
from a host MCP call and proven by read-back; if it cannot be, drop the promise
before execution rather than claiming it. The runtime must not substitute a
different MCP call or silently widen what the Stage claims to preserve.

## Typical call roles

```text
source host MCP
    export the asset to an interchange file

edit host MCP
    edit-host operations such as import, transform, and save

target host MCP
    import or reimport the result

Blender / UE5 MCP
    read-back calls that prove a promised relation
```

The exact calls belong to the Agent-authored Workflow. A Workflow document does not
create them from a fixed table.

## Example Workflow

```text
Stage: export from UE5
    → ue5 MCP export-asset

Stage: edit in Blender
    → blender MCP import
    → blender MCP transform
    → blender MCP save

Stage: return to UE5
    → ue5 MCP import-asset

Stage: validate
    → read-back MCP calls that prove the declared relations
```

If the task only needs a one-way export, the Agent should not add a return Stage.

## Failure / recovery

Preserve every completed artifact, ExecutionResult, and evidence file. Resume the
failed selected call when the Workflow remains valid. If the source, target, call
selection, or preservation promise was wrong, let the Agent author a replacement
Workflow revision.

## Dynamic Stage checklist rule

For each selected Stage, the Agent composes an execution checklist and an
acceptance checklist from the Stage kind, the processing object, the operation
type, the current facts, and the user's requirements, then freezes both in the
WorkflowPlan. The Agent supplies that domain competence; the checklist does not
name Tools, and the final Workflow stores the exact calls.

A call returning `succeeded` is call-level evidence only. The Stage completes
through evidence-backed `ExecutionItemResult` and `CheckResult` aggregation.
