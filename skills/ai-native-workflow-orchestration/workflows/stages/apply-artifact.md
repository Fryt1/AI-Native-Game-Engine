# Stage Contract: Apply Artifact

## Stage ID

```text
stage.apply_artifact
```

## Purpose

Apply a completed Artifact to Blender, UE5, or another declared host.

## Inputs

```text
Artifact Contract
host context
apply parameters
selected host Tool Call
```

## Outputs

```text
host-side result
application evidence
updated artifact / asset reference
```

## Gate

- Artifact exists and its format is supported
- target host is resolved
- the selected host Tool can apply the Artifact
- material / asset replacement policy is explicit

## Tool guidance

The Agent selects an exact concrete Tool from the host Toolset. Examples include
`blender.editor.import-glb` or a project-specific UE5 apply Tool. The Stage
contract must not invent a generic `apply-artifact` operation when the live
Toolset does not publish one.

The Stage receives Artifact references from `stage.provider_artifact`; it does
not rediscover a generator file or silently replace the selected generator or
host Tool.

## Failure / Resume

Keep the Artifact and application logs. Resume at this Stage after repairing the
host input or selected apply Tool. If the Artifact itself is invalid, resume at
`stage.provider_artifact`.

## Dynamic checklist composition

```text
stage_kind: change
knowledge: selected object plus import/modify/configure knowledge
```

Execution checklist must resolve artifact contract, host target, apply parameters, and replacement policy.

Acceptance checklist must prove that host-side state references the artifact correctly and remains readable. Required results need
structured evidence; unresolved facts remain `unknown` and do not complete the
Stage.
