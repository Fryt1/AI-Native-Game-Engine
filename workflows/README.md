# Reusable Workflows

Published Workflow Definitions and lifecycle helpers for the AI Native Game Engine.

A Workflow Definition is reusable guidance and a plan template an Agent can instantiate for a concrete task. Its calls may reference either a project-owned Tool in the Project Tool Registry or a direct MCP Server/tool pair. Blender scripts, UE5 scripts, and ComfyUI graphs are registered as project Tools and live with their owning Toolset under `src/ainative/toolsets/`.

## Table of Contents

- [Current workflows](#current-workflows)
- [Lifecycle](#lifecycle)
- [Maintain](#maintain)
- [Contributing](#contributing)
- [License](#license)

## Current workflows

- `blender-ue5-asset-roundtrip/` — UE5 ↔ Blender asset round-trip (shared guidance: `asset-roundtrip.md`, route `asset_transfer`)
- `blender-mcp-tank-separated/` — experimental/tank workflow draft (shared guidance: `host-operation.md`, route `host_operation`)
- `comfyui-pbr-material-chord/` — CHORD image-to-PBR material maps (graph in `src/ainative/toolsets/comfyui_workflow/graphs/pbr_chord.json`)
- `comfyui-upscale-seedvr2/` — SeedVR2 3B INT8 texture upscale (graph in `src/ainative/toolsets/comfyui_workflow/graphs/upscale_seedvr2.json`)
- `comfyui-material-variants-zimage/` — Z-Image + ControlNet material wear/variants (graph in `src/ainative/toolsets/comfyui_workflow/graphs/material_wear_zimage.json`)
- `comfyui-concept-reference-zimage/` — Z-Image concept/reference image generation (graph in `src/ainative/toolsets/comfyui_workflow/graphs/concept_reference_zimage.json`)
- `comfyui-mesh-projection-chord/` — Blender mesh view render + CHORD material projection (graph in `src/ainative/toolsets/comfyui_workflow/graphs/mesh_projection_chord.json`)

Each published Workflow declares its **Shared guidance** link in `WORKFLOW.md`; when the underlying guidance changes, update every linked package so the two do not diverge.

## Lifecycle

```text
create/validate draft
    → run against projects/fixtures/
    → record machine evidence under artifacts/evidence/
    → record human review when required
    → promote as published
```

Lifecycle helpers live in `scripts/workflows/` (`create_workflow.py`, `validate_workflow.py`, `promote_workflow.py`). To add a reusable workflow, follow [docs/ADDING_A_WORKFLOW.md](../docs/ADDING_A_WORKFLOW.md).

## Maintain

Change a Workflow Definition together with its requirements, plan template, tests, examples, and verification records. Only promote after machine evidence and required human review. When a Workflow's route or lifecycle changes, update both `plan.template.yaml` and the `WORKFLOW.md` Shared guidance line.

## Contributing

Issues and pull requests are welcome on the GitHub repository. Read `AGENTS.md` and `docs/MAINTENANCE.md` before changing behavior.

## License

MIT © [Fry](https://github.com/Fryt1). See [LICENSE](../LICENSE).
