# ComfyUI 游戏工作流研究

> **研究文档，不是实施记录。**
>
> 本文只记录模型/方案调研、硬件适配判断和后续验证计划。本次不安装模型、不升级 ComfyUI、不修改项目代码，也不提交 Git。

- **研究日期：** 2026-09-06
- **研究范围：** 工作流 1、4、5、8、10
- **目标：** 在不使用旧版 SD1.5/旧式 PBR 节点作为主方案的前提下，寻找“当前可用”且适合本机研究的方案。

## 1. 先说判断标准

“最新”需要分成两个维度：

1. **最新总体：** 论文、模型或项目本身较新，质量/研究价值高。
2. **最新可行：** 在当前电脑上能以合理的低分辨率、分块或 CPU offload 完成实际研究。

这两者不是一回事。Pixal3D、TRELLIS.2、Materia 等新方案的研究价值很高，但不能因为它们更新，就假设 RTX 2070 8GB 可以本地运行。

本项目优先选择第二类，并保留第一类作为远程高显存路线。

## 2. 当前本机边界

只读检查得到的本机环境：

```text
整合包根目录：D:\work\Comfyui\ComfyUI-aki-v3.2
ComfyUI 工作区：D:\work\Comfyui\ComfyUI-aki-v3.2\ComfyUI
GPU：NVIDIA GeForce RTX 2070 Laptop，8GB VRAM
系统内存：约 32GB
Python：3.13.11
comfy-cli：1.18.0
ComfyUI MCP：已连接
```

当前本地可发现的相关节点包括：

```text
ChordMaterialEstimation
ChordNormalToHeight
SeedVR2Conditioning
SeedVR2Preprocess
SeedVR2PostProcessing
SeedVR2TemporalChunk
SeedVR2TemporalMerge
ZImageFunControlnet
```

### 版本状态备注

Git checkout 当前显示 `ComfyUI v0.34.5`，但运行中的 `/system_stats` 仍报告 `ComfyUI 0.30.2` 和旧的前端/模板版本。这里先记录为**运行时版本尚未完成读回确认**，不能把模板“可发现”当成已经可运行。

后续如果通过整合包升级，必须重新启动并重新检查运行时版本、节点和工作流兼容性。

## 3. 总体结论

| 工作流 | 研究方向 | 当前“最新可行”方案 | 8GB 结论 | 状态 |
|---|---|---|---|---|
| 1 | 参考图 → PBR | CHORD + Blender 烘焙 | 最有希望，待真实样本验证 | 候选 |
| 4 | 纹理放大 | SeedVR2 3B INT8 | 处于 8GB 临界线，只做小图/分块 | 候选 |
| 5 | 材质磨损/变体 | Z-Image-Turbo INT8 + Union ControlNet Lite 2.1-2602 | 低分辨率、串行运行有希望 | 候选 |
| 8 | 概念图/参考图集 | Blender 控制图 + Z-Image-Turbo 控制生成 | 可以做，但不是严格多视角一致 | 候选 |
| 10 | 已有 Mesh → 材质 | Blender 多视角/UV passes + CHORD + Blender 投影烘焙 | 最稳，适合本机 | 推荐 |

这些是**研究选择**，不是已经通过本机 smoke test 的最终承诺。

---

## 4. 工作流 1：参考图 → PBR 材质贴图

### 4.1 目标

输入一张材质参考图或生成纹理，输出游戏材质需要的核心贴图：

```text
Base Color / Albedo
Normal
Roughness
Metalness
```

可选地从 Normal 推导 Height；AO 不由单张图可靠推断，应在有 Mesh、UV 和几何关系后由 Blender 烘焙。

### 4.2 候选比较

#### CHORD

CHORD 是 Ubisoft La Forge 的 PBR 材质估计工作，目标就是从纹理图像估计 SVBRDF/PBR 材质。官方 ComfyUI 节点已经安装在本机，当前能够发现 `ChordMaterialEstimation` 和 `ChordNormalToHeight`。

官方资料：

- [CHORD 官方仓库](https://github.com/ubisoft/ubisoft-laforge-chord)
- [CHORD ComfyUI 节点](https://github.com/ubisoft/ComfyUI-Chord)
- [CHORD 模型](https://huggingface.co/Ubisoft/ubisoft-laforge-chord)
- [CHORD 论文](https://arxiv.org/abs/2509.09952)

优点：

- 任务与本工作流完全匹配；
- 直接输出 Base Color、Normal、Roughness、Metalness；
- 已有本地节点和示例工作流；
- 显存压力明显低于 7B 级别的通用材质扩散模型。

局限：

- 它是材质估计，不是物理测量；
- 强烈阴影、反射和高光会污染结果；
- 单张图不能可靠恢复真实 AO、曲率和几何细节；
- 模型权重在本机还没有完成可用性验证。

#### Materia

Materia 是更偏现代的 RGB → PBR/G-buffer 方案，输出方向更完整，但官方仓库把它描述为基于 NVIDIA Cosmos 7B 的 ComfyUI 方案，并给出 24GB 显存级别的运行建议。对 RTX 2070 8GB 不作为本地主方案。

- [Materia 官方仓库](https://github.com/NicholaiVogel/comfyui-materia)

#### Material Anything / MatLat / MatMart 类 Mesh-conditioned 方案

这些方案更适合“已有 3D Mesh → UV 一致材质”，研究价值高于简单的单图拆分，但通常需要独立的 PyTorch/Blender/渲染环境，或者显存高于本机边界。它们不应被伪装成当前 ComfyUI 本地可直接运行的替代品。

### 4.3 选择

```text
当前本机选择：CHORD
```

这里的含义是：**CHORD 是当前本机可落地的最新成熟候选，不是宣称它是全球最新模型。**

### 4.4 建议管线

```text
材质参考图
  → 去除明显光照/背景干扰
  → CHORD Material Estimation
  → Base Color / Normal / Roughness / Metalness
  → Normal → Height（可选）
  → Blender UV/几何相关烘焙
  → UE5 Material Instance 预览
```

### 4.5 通过标准

- 四类核心贴图都产生；
- 输出尺寸一致；
- Normal 通道方向和强度可控；
- Roughness 没有全部塌缩到 0 或 1；
- Metalness 没有把非金属大面积误判为金属；
- Base Color 没有明显烘焙光照；
- 有 Mesh 时，AO/Curvature 由 Blender 重新生成。

---

## 5. 工作流 4：纹理放大与细节增强

### 5.1 选择 SeedVR2 3B INT8

当前优先候选是 ByteDance SeedVR2 的 3B INT8 版本，使用 ComfyUI 的单文件模型：

```text
seedvr2_3b_int8_convrot.safetensors
seedvr2_ema_vae_fp16.safetensors
```

官方/一手资料：

- [SeedVR2 官方仓库](https://github.com/ByteDance-Seed/SeedVR2)
- [Comfy-Org SeedVR2 模型重打包](https://huggingface.co/Comfy-Org/SeedVR2)
- [ComfyUI 工作流模板仓库](https://github.com/Comfy-Org/workflow_templates)

选择 3B INT8，而不是 7B 或 FP16，原因是：

- 这是当前仍然较新的专用恢复/放大路线；
- INT8 版本显著降低模型文件和显存压力；
- ComfyUI 已有 SeedVR2 原生节点和模板；
- 3B 是本机唯一值得先做小规模试验的版本。

### 5.2 8GB 适配判断

RTX 2070 8GB 处于临界线，不能直接承诺高分辨率稳定运行。研究阶段应限制为：

```text
输入：512 或 768 边长
batch：1
分块：开启
CPU offload：开启
先做 2x，不直接追求 4K
```

真正的验收不是模型文件能否下载，而是完整工作流能否在不 OOM 的情况下完成。

### 5.3 PBR 数据贴图的特殊规则

SeedVR2 可用于：

- Base Color；
- 普通纹理；
- 概念图；
- 参考图；
- 视觉细节增强。

不应直接让生成式放大器无约束地重绘：

- Normal；
- Roughness；
- Metallic；
- Height。

这些图是数据，不是普通 RGB 图片。建议先使用保守 resize，再做必要的通道校验和 Normal 重新归一化。

### 5.4 备用方案

Z-Image-Turbo 2K 工作流可以用于概念图或视觉纹理增强，但它更偏生成/重绘，不作为 PBR 数据贴图的首选放大器。

---

## 6. 工作流 5：材质磨损与材质变体

### 6.1 选择 Z-Image-Turbo + ControlNet Lite

当前本机优先研究：

```text
Z-Image-Turbo INT8
+
Z-Image-Turbo Fun ControlNet Union 2.1 Lite
```

优先关注的模型变体：

```text
z_image_turbo_int8_convrot.safetensors
Z-Image-Turbo-Fun-Controlnet-Union-2.1-lite-2602.safetensors
```

一手资料：

- [Z-Image 官方仓库](https://github.com/Tongyi-MAI/Z-Image)
- [Comfy-Org Z-Image 模型重打包](https://huggingface.co/Comfy-Org/z_image_turbo)
- [Union ControlNet 2.0/2.1/2602 模型卡](https://huggingface.co/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union-2.0)

Lite 变体的意义是降低控制层数量和运行压力，更适合作为 8GB 机器的研究入口。不要默认使用旧的完整 Union 权重或旧式 SD1.5 ControlNet 管线。

### 6.2 适合生成的变体

```text
新金属 → 生锈金属
装甲 → 泥土覆盖/战损
干燥表面 → 湿润表面
完整涂装 → 掉漆/刮痕
普通混凝土 → 开裂/污染
```

### 6.3 正确管线

```text
原始材质或 UV 纹理
  → 生成/绘制 wear mask
  → Z-Image-Turbo 局部变体
  → ControlNet 保持结构
  → 输出 Base Color 变体
  → CHORD 重新估计 PBR
  → Blender/UE5 做材质预览
```

不要直接对整张纹理无约束重绘，否则容易破坏：

- UV 布局；
- 接缝位置；
- 材质分区；
- 纹理尺度；
- 后续投影关系。

### 6.4 8GB 风险

采用低分辨率、batch 1、串行运行。每次只处理一个材质区域或一个变体。Qwen-Image-Edit 2511/2512 虽然是更强的图像编辑路线，但当前模型规模和显存压力不适合 RTX 2070 作为本地主线。

### 6.5 验收重点

- 变体只发生在 mask 指定区域；
- 物体轮廓和 UV 结构保持；
- 同一个输入可以固定 seed 重现；
- 生成的新 Base Color 可以再次进入 CHORD；
- Roughness/Metalness 变化与磨损语义一致。

---

## 7. 工作流 8：概念图与多视角参考图集

### 7.1 选择

使用工作流 5 的 Z-Image-Turbo + Lite ControlNet，但控制图由 Blender 或其他几何预处理生成：

```text
Blender blockout
  → 正面 Canny / Depth / Gray
  → 侧面 Canny / Depth / Gray
  → 背面 Canny / Depth / Gray
  → 三分之四视角控制图
  → Z-Image-Turbo 生成视觉参考
```

官方 ComfyUI 工作流已有 Z-Image-Turbo ControlNet 方向，支持 Canny、HED、Depth、Pose、MLSD 等控制条件；新版 Lite/2602 权重需要在本地版本和模板兼容后再验证。

- [Z-Image ControlNet 模型卡](https://huggingface.co/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union-2.0)
- [ComfyUI 工作流模板](https://github.com/Comfy-Org/workflow_templates)

### 7.2 可以用于

- 机械资产正/侧/背面参考；
- 装甲和装备拆件；
- 角色服装结构参考；
- 建筑模块参考；
- 材质细节特写；
- Blender 建模前的设计探索。

### 7.3 必须明确的限制

```text
结构控制 ≠ 严格多视角身份一致
```

如果需要真正一致的四视图：

1. 先有 Blender blockout 或真实 Mesh；
2. 用固定相机和控制通道生成每个视角；
3. 固定 seed、提示词和材质描述；
4. 只把 ComfyUI 输出当作设计参考；
5. 最终几何和 UV 仍以 Blender 为准。

纯文本直接生成四张“看起来像同一个物体”的图片，不作为生产资产方法。

### 7.4 8GB 策略

- 每次只生成一个视角；
- 先使用 768 或 1024；
- 不同时开多个扩散分支；
- 优先使用 Canny/Depth/Gray，减少自由度；
- 用 Blender 负责拼接参考板，不让模型自己猜版式。

---

## 8. 工作流 10：已有 Mesh → 材质投影

### 8.1 结论

当前没有找到一个同时满足以下条件的单一模型：

```text
较新
有成熟生态
有 ComfyUI 本地集成
RTX 2070 8GB 能稳定运行
能处理游戏资产的 UV/几何关系
```

因此本机不采用“一个模型包办全部”的方案，而采用几何感知混合管线。

### 8.2 推荐管线

```text
已有 Blender Mesh
  → 检查/整理 UV
  → 固定相机渲染多视角
  → 输出 Base render / Normal / Depth / Gray / UV辅助图
  → CHORD 估计材质属性
  → Blender 将各视角结果投影/合并回 UV
  → Blender 烘焙 AO / Curvature / 高低模 Normal
  → 导出贴图和材质
  → UE5 Material Instance 预览和验证
```

这条路线的职责划分是：

```text
ComfyUI：材质外观估计、缺失区域生成、参考图修复
Blender：Mesh、UV、投影、烘焙、贴图合并
UE5：材质组装、实例参数、引擎内验证
```

### 8.3 为什么不选 Pixal3D/TRELLIS.2 作为本机方案

Pixal3D 和 TRELLIS.2 是当前很重要的图像到 3D/纹理研究方向，Pixal3D 也明确面向带材质的 3D 资产。但它们的目标是完整 3D 生成，不是简单的 PBR map 拆分；本机 8GB 不足以把它们当作稳定的本地基础设施。

- [Pixal3D 官方仓库](https://github.com/TencentARC/Pixal3D)
- [TRELLIS.2 官方仓库](https://github.com/microsoft/TRELLIS.2)
- [Comfy-Org Pixal3D 模型](https://huggingface.co/Comfy-Org/Pixal3D)
- [Comfy-Org TRELLIS.2 模型](https://huggingface.co/Comfy-Org/TRELLIS.2)

它们保留为：

```text
远程 24GB+ GPU
或未来高显存台式机
```

而不是当前 RTX 2070 的本地必选依赖。

### 8.4 验收重点

- 投影结果没有明显视角接缝；
- UV 岛边缘没有空洞；
- Base Color、Normal、Roughness、Metalness 位置一致；
- AO/Curvature 来源明确且由 Blender 生成；
- UE5 中使用同一套材质参数时，外观与 Blender 预览基本一致；
- 贴图能导出为项目约定的命名、分辨率和通道格式。

---

## 9. 最终选择与排除

### 9.1 当前本机主线

```text
工作流 1：CHORD
工作流 4：SeedVR2 3B INT8（小分辨率/分块试验）
工作流 5：Z-Image-Turbo INT8 + Union ControlNet Lite
工作流 8：Blender 控制图 + Z-Image-Turbo
工作流 10：Blender 几何管线 + CHORD
```

### 9.2 不作为本机主线

```text
Materia：直接 PBR 方向很对，但显存门槛高
Pixal3D：新且有价值，但属于高显存 3D 资产路线
TRELLIS.2：新且有价值，但属于高显存 3D 生成路线
Material Anything：Mesh-conditioned，需独立环境
MatLat/MatMart：研究价值高，当前不是 8GB ComfyUI 路线
旧 SD1.5 ControlNet：不作为新主线
旧 Real-ESRGAN/4x-UltraSharp：只作为传统 fallback，不作为研究主线
```

## 10. 建议验证顺序

研究结论转实施时，再按以下顺序验证：

1. 先用已经存在的 CHORD 节点和一张小材质图跑工作流 1；
2. 确认 CHORD 权重能完整加载，再记录 VRAM、耗时和四类输出；
3. 再验证 SeedVR2 3B INT8 的 512/768 单图放大；
4. 再验证 Z-Image-Turbo INT8 的基础生成；
5. 最后接入 Lite ControlNet，先做单个 wear mask；
6. 用 Blender blockout 生成工作流 8 的四视角控制图；
7. 用真实 Mesh 做工作流 10 的多视角投影和 Blender 烘焙；
8. 最后才将五条路线串成项目 Route。

每次验证必须记录：

```text
模型文件名
模型来源
ComfyUI/整合包版本
输入分辨率
输出分辨率
VRAM 峰值
系统内存
耗时
是否 OOM
输出路径
人工质量结论
```

## 11. 当前研究状态

```text
已完成：候选路线筛选、硬件边界判断、主线/远程路线区分
未完成：五条路线的真实本机 smoke test、质量对比、最终 workflow JSON
本次操作：只写本研究文档，不升级、不安装、不下载、不提交 Git
```

## 12. 一手来源

- [Ubisoft La Forge CHORD](https://github.com/ubisoft/ubisoft-laforge-chord)
- [ComfyUI-Chord](https://github.com/ubisoft/ComfyUI-Chord)
- [CHORD on Hugging Face](https://huggingface.co/Ubisoft/ubisoft-laforge-chord)
- [ByteDance SeedVR2](https://github.com/ByteDance-Seed/SeedVR2)
- [SeedVR2 ComfyUI repack](https://huggingface.co/Comfy-Org/SeedVR2)
- [Tongyi-MAI Z-Image](https://github.com/Tongyi-MAI/Z-Image)
- [Z-Image ComfyUI repack](https://huggingface.co/Comfy-Org/z_image_turbo)
- [Z-Image Fun ControlNet](https://huggingface.co/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union-2.0)
- [TencentARC Pixal3D](https://github.com/TencentARC/Pixal3D)
- [Comfy-Org Pixal3D](https://huggingface.co/Comfy-Org/Pixal3D)
- [Microsoft TRELLIS.2](https://github.com/microsoft/TRELLIS.2)
- [Comfy-Org TRELLIS.2](https://huggingface.co/Comfy-Org/TRELLIS.2)
- [3DTopia Material Anything](https://github.com/3DTopia/MaterialAnything)
- [Materia for ComfyUI](https://github.com/NicholaiVogel/comfyui-materia)
- [ComfyUI workflow templates](https://github.com/Comfy-Org/workflow_templates)