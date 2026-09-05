# Stage Knowledge Index

This directory supplies composable knowledge for Agent-authored dynamic Stages.
It is guidance, not executable code and not a second Tool Registry.

Load knowledge in this order:

```text
Stage kind
    + processing object
    + operation type
    + current state and user requirements
    → execution checklist
    + acceptance checklist
```

## Stage kinds

- `stage-kinds/change.md`
- `stage-kinds/investigation.md`
- `stage-kinds/planning.md`

## Processing objects

- `objects/geometry.md`
- `objects/skeleton-binding.md`
- `objects/animation.md`
- `objects/material-texture.md`
- `objects/effects-simulation.md`
- `objects/scene-level.md`
- `objects/references-metadata.md`
- `objects/project-runtime-performance.md`

## Operations

- `operations/create.md`
- `operations/configure.md`
- `operations/import.md`
- `operations/export.md`
- `operations/modify.md`
- `operations/repair.md`
- `operations/optimize.md`
- `operations/convert.md`
- `operations/batch.md`
- `operations/publish.md`

The Agent freezes both checklists before a change Stage causes side effects.
Investigation Stages may add evidence-gathering items as facts change, but their
scope, stop condition, and acceptance rules remain explicit.
