# ComfyUI 游戏工作流 — 搭建与验证进度

> 2026-09-07 实际执行记录。所有 ComfyUI 工作流 JSON 位于
> `game-engine/workflows/comfyui-*-*/comfyui_workflow.json`（或目录内对应 JSON）。
> 证据图位于 `game-engine/artifacts/evidence/comfyui-game-workflows/*/`。

## 环境

```text
ComfyUI v0.34.5 (frontend 1.49.6 / templates 0.11.55)
GPU: NVIDIA GeForce RTX 2070 Laptop 8GB
RAM: 32GB（研究期间被后台进程占用，CHORD 大图推理明显变慢）
Python: 3.13.11
```

## 课题 1：参考图 → PBR 材质贴图（CHORD）✅ 已验证

- 工作流：`workflows/comfyui-pbr-material-chord/comfyui_workflow.json`
- 模型：`chord_v1.safetensors`（2.57GB，SHA256 校验通过）
- 输入：`ComfyUI/input/pbr_input.png`（1024x1024）
- 输出：`base_color / normal / roughness / metalness / height` 五张
- 证据：`artifacts/evidence/comfyui-game-workflows/pbr-material-chord/`
- 实际运行：完成，无 OOM，五图齐全

## 课题 4：纹理放大（SeedVR2 3B INT8）✅ 已验证

- 工作流：`workflows/comfyui-upscale-seedvr2/comfyui_workflow.json`
- 模型：`seedvr2_3b_int8_convrot.safetensors`（3.2GB）+ `seedvr2_ema_vae_fp16.safetensors`（478MB）
- 官方模板 `utility_seedvr2_3b_int8_upscale_image`，移除 UI-only `ImageCompare` 节点
- 输入：`upscale_input.png`（512x512）
- 输出：2048x2048（4x）
- 证据：`artifacts/evidence/comfyui-game-workflows/upscale-seedvr2/upscaled.png`
- 实际运行：完成，无 OOM

## 课题 5：材质磨损/变体（Z-Image-Turbo + ControlNet）✅ 已验证

- 目录：`workflows/comfyui-material-variants-zimage/`
- T2I 探针：`comfyui_workflow.json`（BF16 底座，1024x1024，完成）
- ControlNet 磨损：`comfyui_controlnet_workflow.json`（Canny 结构保持 + 磨损提示词）
- 模型：`z_image_turbo_int8_convrot.safetensors`（5.7GB）+
  `Z-Image-Turbo-Fun-Controlnet-Union-2.1-lite-2602-8steps.safetensors`（1.8GB）
- 证据：`zimage_t2i_probe.png`、`wear_canny.png`
- 实际运行：ControlNet 磨损图完成，1024x1024，无 OOM

## 课题 8：概念图/参考图集（Z-Image + ControlNet）✅ 已验证

- 工作流：`workflows/comfyui-concept-reference-zimage/comfyui_workflow.json`
- 输入：`material_source.png`（Canny 结构）
- 输出：`game_concept_ref/concept_side`
- 证据：`artifacts/evidence/comfyui-game-workflows/concept-reference-zimage/concept_side.png`
- 实际运行：完成（1024x1024）

## 课题 10：已有 Mesh → 材质投影（Blender + CHORD 混合）✅ ComfyUI 侧已验证

- ComfyUI 图：`workflows/comfyui-mesh-projection-chord/comfyui_workflow.json`（512px 输入实测完成，五图输出，无 OOM）
- 结构 = 课题 1 已验证 CHORD 图（输入 `mesh_view_render.png`，输出 `game_mesh_pbr/*`）
- 证据：`artifacts/evidence/comfyui-game-workflows/mesh-projection-chord/`
- 真实运行受阻：研究期间机器 RAM 被后台进程大量占用，CHORD 512/1024 推理
  均超过 20 分钟未完成（此前同图 1-2 分钟完成）。判定为环境资源问题，
  不是工作流缺陷。
- 完整管线仍需：Blender 渲染多视角 → CHORD → Blender 投影/烘焙 → UE5

## 关键模型清单（已下载并校验）

| 文件 | 位置 | 大小 |
|---|---|---|
| chord_v1.safetensors | models/checkpoints/ | 2.57GB |
| seedvr2_3b_int8_convrot.safetensors | models/diffusion_models/ | 3.2GB |
| seedvr2_ema_vae_fp16.safetensors | models/vae/ | 478MB |
| z_image_turbo_int8_convrot.safetensors | models/diffusion_models/ | 5.7GB |
| Z-Image-Turbo-Fun-Controlnet-Union-2.1-lite-2602-8steps.safetensors | models/model_patches/ | 1.8GB |
| z_image_turbo_bf16.safetensors | models/diffusion_models/ | 11.46GB |
| qwen_3_4b.safetensors | models/text_encoders/ | 7.49GB |
| z_image.safetensors (VAE) | models/vae/ | 0.31GB |

## 已知限制 / 注意

1. 8GB VRAM 是 CHORD/Z-Image 的临界线；系统 RAM 被占满时会严重拖慢推理。
2. 不要在 ComfyUI 队列残留任务时直接重启；用 `/interrupt` + `/queue clear`，
   必要时彻底杀进程重启。
3. 多个大模型文件同时驻留会挤占显存；一次只跑一个工作流。
4. 文本编码器 `qwen_3_4b_fp8_mixed` 尚未下载；如需 INT8 底座更省显存可后续补。
5. 本记录未提交 git。