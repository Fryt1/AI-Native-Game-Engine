# Stage Contract: Return to Target

## Stage ID

```text
stage.return_to_target
```

## Purpose

Publish the modified artifact to the target host through the transfer branch
selected by the Agent and record import or reimport evidence.

## Inputs

```text
modified artifact
Transfer Manifest or Artifact Contract
target host
selected transfer Tool Call
```

## Outputs

```text
target asset result
import / reimport evidence
updated Manifest facts
```

## Tool guidance

The Agent calls the selected transfer Tool, for example:

```text
transfer.assetsbridge.return_to_target
transfer.direct.return_to_target
```

A target-host import may be an internal part of that Tool when it is one
coherent transfer operation. If it needs independent evidence or recovery, the
Agent may add a separate target-host Tool Call in the Stage.

## Gate

The target host, target project, and target operation must be authorized and
identifiable. A file existing on disk is not evidence that the target asset was
updated.

## Failure / Resume

A target import or reimport error stops the Stage. Preserve the modified artifact
and Manifest, repair the selected Tool implementation, and retry or re-plan.

## Dynamic checklist composition

```text
stage_kind: change
knowledge: selected object plus export/import/publish knowledge
```

Execution checklist must resolve modified artifact, target, branch, overwrite, and import policy.

Acceptance checklist must prove that target result exists, is correct, and import/reimport evidence has no blocking errors. Required results need
structured evidence; unresolved facts remain `unknown` and do not complete the
Stage.
