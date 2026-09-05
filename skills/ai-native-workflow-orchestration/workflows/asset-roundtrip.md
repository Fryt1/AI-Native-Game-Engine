# Workflow Guidance: UE5–Blender Asset Roundtrip

## Route Family

```text
asset_transfer
```

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
Transfer Manifest
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
choose an allowed transfer branch
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
Stages. Any state-changing action must be an explicit Tool Call.

## Transfer branch

The Agent selects exactly one transfer Toolset after reading the preservation
and loss policy:

```text
transfer.assetsbridge
    preserve bridge-observable identity, mappings, and relations

transfer.direct
    file-level exchange when its known loss is explicitly acceptable
```

AssetsBridge and Direct Transfer are sibling choices. A failed branch must not
be silently replaced by the other branch.

## Typical Toolset roles

```text
transfer.assetsbridge / transfer.direct
    transfer_to_edit_host
    return_to_target

blender.editor
    edit-host operations such as translate-active or save-mainfile

validation.workflow
    validate the declared relations and evidence
```

The exact Tool Calls belong to the Agent-authored plan. A Workflow document does
not create them from a fixed table.

## Example plan

```text
Stage: transfer to Blender
    → transfer.assetsbridge.transfer_to_edit_host

Stage: edit the asset
    → blender.editor.translate-active

Stage: return to UE5
    → transfer.assetsbridge.return_to_target

Stage: validate
    → validation.workflow.validate
```

If the task only needs a one-way export, the Agent should not add a return Stage.
If the task does not promise identity or relation preservation, Direct Transfer
may be appropriate when its loss policy passes.

## Failure / recovery

Preserve every completed artifact, Manifest, ExecutionResult, and evidence file.
Resume the failed selected Tool when the plan remains valid. If the source,
target, branch, or preservation promise was wrong, supersede the plan and let
the Agent author a new revision.

## Dynamic Stage checklist rule

For each selected Stage, the Agent loads the relevant `knowledge/stage-kinds`,
`knowledge/objects`, and `knowledge/operations` documents, then freezes an
execution checklist and an acceptance checklist in the WorkflowPlan. Checklist
knowledge does not name Tools; the final plan stores exact Tool Calls from the
live Registry.

A Tool returning `succeeded` is call-level evidence only. The Stage completes
through evidence-backed `ExecutionItemResult` and `CheckResult` aggregation.
