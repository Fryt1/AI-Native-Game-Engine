# ComfyUI Mesh Material Projection — Blender + CHORD

<!-- provenance: this Workflow Definition implements the shared guidance below. When the guidance changes, review and update this file; do not let the two diverge. -->

- **Shared guidance:** [`provider-artifact-apply.md`](../../skills/ai-native-workflow-orchestration/workflows/provider-artifact-apply.md) (route: `artifact_pipeline`)

Hybrid workflow: use an existing Blender mesh, render views/passes, estimate PBR
maps with CHORD, and project/bake back to UV in Blender.

## Status

- ComfyUI graph: VERIFIED — full runtime run completed (512px input, five maps output, no OOM)
- Evidence: `artifacts/evidence/comfyui-game-workflows/mesh-projection-chord/`
- Note: on this 8GB machine CHORD inference is slow (up to ~20 min) when system RAM is under pressure; run when machine is idle
- Full mesh pipeline requires a Blender mesh fixture and is NOT yet run end-to-end

## Pipeline

```text
existing Blender mesh
  -> fix/unwrap UV
  -> neutral multi-view render (Base render / Normal / Depth / Gray / UV pass)
  -> CHORD material estimation per view (this ComfyUI graph)
  -> Blender project/merge maps back into UV space
  -> Blender bake AO / curvature / high-low normal
  -> UE5 material instance and preview
```

## Files

- Canonical graph: `src/ainative/toolsets/comfyui_workflow/graphs/mesh_projection_chord.json`

## Input contract

- One neutral view render from Blender (no strong cast shadows/highlights)
- Same model/UV retained in Blender; output maps are estimate, not final

## Blender responsibilities (not ComfyUI)

- Geometry, UV layout, projection, baking, AO/curvature
- Combining per-view CHORD estimates into UV space
- High-poly to low-poly normal baking

## Why not Pixal3D/TRELLIS.2

Those are newer image-to-3D/PBR routes but exceed 8 GB reliable local budget.
This hybrid keeps geometry authority in Blender while using CHORD for appearance.

## Validation

1. CHORD graph validates (done)
2. Blender renders a test mesh view to `ComfyUI/input/mesh_view_render.png`
3. Run graph, verify five maps
4. Blender projection/bake produces UV-space maps without seams
5. UE5 material instance preview passes
