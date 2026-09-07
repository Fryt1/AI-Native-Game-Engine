# ComfyUI Material Wear/Variants — Z-Image-Turbo + Fun ControlNet

<!-- provenance: this Workflow Definition implements the shared guidance below. When the guidance changes, review and update this file; do not let the two diverge. -->

- **Shared guidance:** [`host-operation.md`](../../skills/ai-native-workflow-orchestration/workflows/host-operation.md) (route: `host_operation`)

Reusable workflow definition for creating material wear variants (rust, dust,
wet, damage) from an existing material texture on an 8 GB GPU.

## Status

- ComfyUI v0.34.5 verified
- Base T2I probe (BF16, 1024x1024) completed
- VERIFIED end-to-end: ControlNet Canny wear variant completed (INT8 + Lite 2602) 1024x1024, no OOM

## Files

- Canonical wear graph: `src/ainative/toolsets/comfyui_workflow/graphs/material_wear_zimage.json` (Canny control, verified run)

## Input contract

- Source material image (e.g. CHORD Base Color output)
- Wear prompt describes the variant and what should NOT change
- Canny threshold keeps overall structure

## Material variants of interest

```text
clean metal -> rust
clean metal -> dust / dirt
dry surface -> wet / rain
intact paint -> scratches / chipped paint
clean concrete -> cracks / grime
```

## Important limits

- Z-Image ControlNet preserves structure, not exact UV/material identity.
- For a production wear mask, combine with a mask/inpaint workflow so changes
  stay inside the requested region.
- Never apply wear generation to Normal/Roughness/Metallic directly; regenerate
  PBR maps from the new Base Color with CHORD instead.

## 8 GB notes

- INT8 diffusion model reduces VRAM; BF16 also ran via offload.
- 512-768 input; batch 1; sequential variants.
- Do not run multiple diffusion branches at once.

## Validation

1. `validate_workflow` passes on live install
2. Base T2I probe completed (evidence: material-variants-zimage/zimage_t2i_probe.png)
3. ControlNet run completes without OOM
4. Outputs preserve silhouette/material layout and show only requested wear
5. New Base Color is fed through CHORD to regenerate PBR maps

## Evidence

`artifacts/evidence/comfyui-game-workflows/material-variants-zimage/`
