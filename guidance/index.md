# Workflow Guidance Inventory

Maintainer-only inventory. It is not runtime dispatch input and not a registry.

## Guidance

- `host-operation.md`
- `asset-edit.md`
- `asset-roundtrip.md`
- `native-blender-operation.md`
- `provider-artifact-apply.md`
- `failure-recovery.md`

## Templates

- `templates/workflow-template.md` — copy to `guidance/<name>.md` to write a lifecycle
- `templates/workflow-plan-template.json` — copy and fill in to author a Workflow
- `templates/workflow-plan-template.md` — the same shape with field notes and the 8 stability rules

Host capabilities — Blender, UE5, and ComfyUI — are reached through their own MCP
servers by the Agent's MCP client. This package documents what to call; it ships
no executable Toolset.

## Maintenance rules

1. Add or change a guidance document when a repeatable macro lifecycle deserves a
   name; guidance states invariants, not a universal Step list.
2. Keep each guidance document's lifecycle distinct. Do not maintain per
   host/object/operation combinations as separate documents — the Agent composes
   each Stage from Stage kind, processing object, operation type, current facts,
   and the user's requirements.
3. Confirm the exact calls and acceptance feasibility before change-side effects.
4. Update this inventory and the integrity gate when canonical files change.
5. A guidance document carries no dependency declaration of its own. Host and
   model prerequisites live in `docs/DEPENDENCIES.md`; review a guidance file's
   invariants when that contract changes.
