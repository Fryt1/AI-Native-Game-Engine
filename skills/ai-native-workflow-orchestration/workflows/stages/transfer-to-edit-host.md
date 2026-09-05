# Stage Contract: Transfer to Edit Host

## Stage ID

```text
stage.transfer_to_edit_host
```

## Purpose

Make the asset available to the selected edit host while respecting the
Workflow's preservation and acceptable-loss policy.

## Inputs

```text
resolved asset reference
edit host
selected transfer Toolset
preservation policy
```

## Outputs

```text
edit-host artifact
Transfer Manifest facts
transfer evidence
```

## Gate

- source asset is resolved
- edit host is identified
- selected transfer Toolset is ready
- preservation and acceptable-loss policy is explicit

## Tool guidance

The Agent selects one exact Tool Call from one of these sibling Toolsets:

```text
transfer.assetsbridge.transfer_to_edit_host
transfer.direct.transfer_to_edit_host
```

AssetsBridge is required when the Workflow promises relations that Direct
Transfer cannot preserve. Direct Transfer is valid only when its known loss is
explicitly acceptable. The runtime must not replace the selected branch.

## Failure / Resume

A transfer error stops this Stage. Preserve the source artifact, Manifest, and
error evidence. Retry the selected Tool or author a new plan revision after
repairing the selected Backend.

## Dynamic checklist composition

```text
stage_kind: change
knowledge: selected object plus export/import or convert knowledge
```

Execution checklist must resolve source, format, preservation/loss, and edit-host prerequisites.

Acceptance checklist must prove that edit-host representation exists and declared preservation/loss evidence is recorded. Required results need
structured evidence; unresolved facts remain `unknown` and do not complete the
Stage.
