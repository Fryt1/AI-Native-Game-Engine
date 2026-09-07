# ComfyUI Texture Upscale — SeedVR2 3B INT8

<!-- provenance: this Workflow Definition implements the shared guidance below. When the guidance changes, review and update this file; do not let the two diverge. -->

- **Shared guidance:** [`host-operation.md`](../../skills/ai-native-workflow-orchestration/workflows/host-operation.md) (route: `host_operation`)

Reusable workflow definition for 2x/4x texture upscaling on an 8 GB GPU.

## Status

- ComfyUI v0.34.5 verified
- `seedvr2_3b_int8_convrot.safetensors` + `seedvr2_ema_vae_fp16.safetensors` installed
- Smoke test: 512x512 -> 2048x2048 completed without OOM
- Evidence: `artifacts/evidence/comfyui-game-workflows/upscale-seedvr2/`

## Graph

Canonical graph: `src/ainative/toolsets/comfyui_workflow/graphs/upscale_seedvr2.json`

```text
LoadImage (upscale_input.png)
  -> SeedVR2 subgraph: SeedVR2Preprocess -> VAEEncodeTiled (512, overlap 128)
  -> UNETLoader seedvr2_3b_int8_convrot + VAELoader seedvr2_ema_vae_fp16
  -> KSampler 1 step euler/simple
  -> VAEDecodeTiled -> SeedVR2PostProcessing
  -> ResizeImageMaskNode scale-by-multiplier 4x
  -> SaveImage (game_upscale/upscaled)
```

## Input contract

- RGB image (alpha dropped by SeedVR2 preprocessing)
- Smoke size: 512x512 (use 768 only after 512 passes)
- Batch 1

## Output contract

- 4x resolution, same aspect ratio
- For data maps (Normal/Roughness/Metallic/Height) prefer conservative
  resize, not generative upscale.

## Validation

1. `validate_workflow` passes on the live ComfyUI install
2. One real run completes at 512
3. Output saved under `game_upscale/`
4. Visual check: edges and material boundaries preserved
