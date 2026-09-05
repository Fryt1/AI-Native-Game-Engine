# Reusable Workflows

This directory contains **published Workflow Definitions**, not runtime Tool
implementations.

A Workflow Definition is reusable guidance and a plan template that an Agent can
instantiate for a concrete task. Its calls may reference either a project-owned
Tool in the Tool Registry or a direct MCP Server/tool pair.

Blender scripts, UE5 scripts, and ComfyUI graphs are registered as project Tools
and live with their owning Toolset under `src/ainative/toolsets/`.

## Lifecycle

```text
artifacts/scratch/workflow-drafts/<id>/<revision>/
    -> validate structure and dependencies
    -> run against projects/fixtures/
    -> write machine evidence under artifacts/evidence/
    -> record human review
    -> promote to workflows/<id>/
```

A published Workflow package normally contains:

```text
<workflow-id>/
├── WORKFLOW.md
├── plan.template.yaml
├── requirements.yaml
├── examples/
├── tests/
└── verification/
```

Use the lifecycle scripts from the project root:

```powershell
python scripts\workflows\create_workflow.py blender-ue5-asset-roundtrip
python scripts\workflows\validate_workflow.py artifacts\scratch\workflow-drafts\blender-ue5-asset-roundtrip\r1
python scripts\workflows\promote_workflow.py artifacts\scratch\workflow-drafts\blender-ue5-asset-roundtrip\r1
```
