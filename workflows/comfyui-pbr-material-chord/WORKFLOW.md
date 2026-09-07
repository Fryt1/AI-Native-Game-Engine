# ComfyUI PBR Material — CHORD

<!-- provenance: this Workflow Definition implements the shared guidance below. When the guidance changes, review and update this file; do not let the two diverge. -->

- **Shared guidance:** [`provider-artifact-apply.md`](../../skills/ai-native-workflow-orchestration/workflows/provider-artifact-apply.md) (route: `artifact_pipeline`)

This Workflow Definition is the first executable ComfyUI workflow in the game
asset pipeline. It converts one material reference image into the core PBR maps
needed by Blender/UE5.

## Intent

```text
reference texture → CHORD → Base Color / Normal / Roughness / Metalness
                         └→ Normal → Height
```

CHORD estimates material appearance. It does not replace Blender's geometry-
aware AO, curvature, high/low normal baking, UV validation, or final texture
packing.

## ComfyUI graph

- Canonical graph: `src/ainative/toolsets/comfyui_workflow/graphs/pbr_chord.json`
- Input node: `LoadImage`
- Model node: `ChordLoadModel`
- Estimator: `ChordMaterialEstimation`
- Height derivation: `ChordNormalToHeight`
- Outputs: five `SaveImage` nodes under `game_pbr/`

## Prerequisites

```text
ComfyUI-Chord custom node
chord_v1.safetensors in ComfyUI/models/checkpoints
an input image uploaded to ComfyUI/input as pbr_input.png
```

The graph intentionally names the checkpoint `chord_v1.safetensors`. Until the
checkpoint is present, ComfyUI will show a missing-model validation error; that
is a dependency failure, not a graph-wiring failure.

## Input contract

- One material-focused image.
- Prefer diffuse-looking, evenly lit, tileable or near-tileable input.
- Avoid a full object shot with background, cast shadows, and specular highlights
  when the goal is a reusable surface material.
- Initial validation should use 512–1024 px input and batch size 1.

## Output contract

```text
game_pbr/base_color_*.png
game_pbr/normal_*.png
game_pbr/roughness_*.png
game_pbr/metalness_*.png
game_pbr/height_*.png
```

The exact ComfyUI output filename may include the batch counter. The five maps
must keep the same source identity and resolution.

## Validation

1. Validate the graph against the live ComfyUI catalog.
2. Confirm `chord_v1.safetensors` is present before execution.
3. Upload one test image as `pbr_input.png`.
4. Run the graph once at the initial resolution.
5. Read back every output path and inspect all five maps.
6. If a Mesh exists, generate AO/curvature/production normals in Blender and
   compare the result in UE5.

## Failure rules

- Missing checkpoint: stop and report the exact required model path.
- Missing node: stop; do not substitute an older PBR node silently.
- OOM: lower input resolution, call ComfyUI memory freeing between runs, and
  retry batch 1; do not change the semantic map contract.
- Bad material estimate: fix the input lighting/background before adding more
  model stages.

## Evidence

Execution evidence belongs under:

```text
artifacts/evidence/comfyui-game-workflows/pbr-material-chord/
```

Do not promote this workflow to a project Route until a real run produces all
five outputs and the Blender/UE5 preview passes.
