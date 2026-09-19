# Workflow Guidance Inventory

Maintainer-only inventory. It is not runtime dispatch input and not a registry.

## Guidance

- `host-operation.md`
- `asset-edit.md`
- `asset-roundtrip.md`
- `native-blender-operation.md`
- `provider-artifact-apply.md`
- `failure-recovery.md`

## Guidance forms

Guidance may be a single document or a directory. Prose is the **floor, not the
ceiling**: a lifecycle that is only a document is the degenerate case of a skill.
A richer one may hold scripts, schemas, data, or templates alongside its documents.

```text
guidance/<name>.md          a single document
guidance/<name>/            a directory, using its entry document
    README.md               read first; also index.md, SKILL.md, GUIDANCE.md
    ...                     scripts, schemas, data, templates
```

A directory is tried before a document, so a name can be promoted from one form to
the other without changing how a task refers to it.

## Templates

- `templates/guidance-template.md` — the shape of a guidance document

There is no Workflow template. `templates/workflow.schema.json` is the definition of
the Workflow data structure, and a template beside it would be a second description
of the same thing — two descriptions drift, and this repository has paid for that
twice. The schema is the one an author or an AI can be checked against.

Host capabilities — Blender, UE5, and ComfyUI — are reached through their own MCP
servers by the Agent's MCP client. This package documents what to call; it ships
no executable Toolset.

## Maintenance rules

1. Add or change a guidance document when a repeatable macro lifecycle deserves a
   name; guidance states invariants, not a fixed sequence of nodes.
2. Keep each guidance document's lifecycle distinct. Do not maintain per
   host/object/operation combinations as separate documents — the Agent composes
   each STAGE from Stage kind, processing object, operation type, current facts,
   and the user's requirements, and decides for itself how to group nodes into
   STAGE leaves and WORKFLOW composites.
3. Confirm the exact calls and acceptance feasibility before change-side effects.
4. Update this inventory and the integrity gate when canonical files change.
5. A guidance document carries no dependency declaration of its own. Host and
   model prerequisites live in `docs/DEPENDENCIES.md`; review a guidance file's
   invariants when that contract changes.
