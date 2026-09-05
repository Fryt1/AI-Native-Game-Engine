# Reusable Workflows

Published Workflow Definitions, not runtime Tool implementations.

A Workflow Definition is reusable guidance and a plan template an Agent can instantiate for a concrete task. Its calls may reference either a project-owned Tool in the Project Tool Registry or a direct MCP Server/tool pair.

Blender scripts, UE5 scripts, and ComfyUI graphs are registered as project Tools and live with their owning Toolset under `src/ainative/toolsets/`.

## Lifecycle

```text
create/validate draft
    → run against projects/fixtures/
    → record machine evidence under artifacts/evidence/
    → record human review when required
    → promote as published
```

Lifecycle helpers live in `scripts/workflows/`.

## Current workflows

- `blender-ue5-asset-roundtrip/` — UE5 ↔ Blender asset round-trip
- `blender-mcp-tank-separated/` — experimental/tank workflow draft (see its README)

## Maintain

Change a Workflow Definition together with its requirements, plan template, tests, examples, and verification records. Only promote after machine evidence and required human review.
