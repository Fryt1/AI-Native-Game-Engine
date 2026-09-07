# ComfyUI Concept / Reference Image — Z-Image-Turbo + Fun ControlNet

<!-- provenance: this Workflow Definition implements the shared guidance below. When the guidance changes, review and update this file; do not let the two diverge. -->

- **Shared guidance:** [`host-operation.md`](../../skills/ai-native-workflow-orchestration/workflows/host-operation.md) (route: `host_operation`)

Generate a reference/concept image from a source image plus prompt, preserving
the source structure through Canny control.

## Status

- ComfyUI v0.34.5 verified
- Run completed 1024x1024, no OOM
- Evidence: `artifacts/evidence/comfyui-game-workflows/concept-reference-zimage/`

## Intent

```text
control/source image + concept prompt
  -> Canny structure control
  -> Z-Image-Turbo (INT8) + Fun ControlNet Lite
  -> reference image output
```

## Files

- Canonical graph: `src/ainative/toolsets/comfyui_workflow/graphs/concept_reference_zimage.json`

## Input contract

- Source/silhouette input uploaded as `ComfyUI/input/material_source.png`
- Prompt describes target reference (viewpoint, subject, material)

## Limits

- Structure control does NOT guarantee strict multi-view identity across runs.
- Blender blockout remains authoritative for actual production reference sheets.

## Validation

1. `validate_workflow` passes on live install
2. Run completes without OOM
3. Outputs preserve source silhouette/layout
4. Evidence recorded under `artifacts/evidence/comfyui-game-workflows/concept-reference-zimage/`
