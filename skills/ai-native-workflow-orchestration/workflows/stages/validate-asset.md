# Stage Contract: Validate Asset Transfer

## Stage ID

```text
stage.validate_asset
```

## Purpose

Validate the relations explicitly declared by an asset transfer Workflow.

## Inputs

```text
source / edit / target artifacts
Transfer Manifest
operation evidence
preservation and acceptable-loss policy
```

## Outputs

```text
preserved_relations
lost_relations
warnings
errors
Loss Report when applicable
```

## Tool guidance

The Agent selects an exact Tool from `validation.workflow`, such as
`validation.workflow.validate`. The concrete implementation may be
`ManifestValidator`, `AssetsBridgeValidator`, or a future host-specific
validator.

## Current AssetsBridge checks

`AssetsBridgeValidator` currently checks the `from-blender.json` payload for:

```text
matching objectId / model identity
objectMaterials presence
worldData location / rotation / scale
```

It returns:

```text
preserved_relations
lost_relations
warnings
errors
```

## Gate

- source, edit, and target evidence are available
- the declared preservation / acceptable-loss policy is explicit
- the selected validator can inspect the requested relation facts

## Required validation items when requested

```text
geometry
asset path / object identity
material slots
Transform
Skeleton / Morph
textures / material policy
import / reimport result
artifact existence
```

A relation is preserved only when target evidence supports it. Do not infer
preservation from a successful process exit or the existence of a GLB file.

## Failure / Resume

Validation failure resumes at this Stage after preserving source and target
evidence. If the payload itself is wrong, the Agent may re-plan the owning
transfer or modification Stage.

## Dynamic checklist composition

```text
stage_kind: investigation
knowledge: all relevant object and operation acceptance knowledge
```

Execution checklist must collect source/target facts and relation evidence.

Acceptance checklist must prove that every required preservation/loss item is pass, warn, fail, unknown, or needs_human. Required results need
structured evidence; unresolved facts remain `unknown` and do not complete the
Stage.
