# Validation Report

> Latest validation: September 6, 2026（宿主软件经 MCP 到达；本仓库只保留无宿主依赖的
> 清单契约、校验与验收引擎）。

## Scope

记录本仓库当前形态的验证：结构化验收，以及宿主 MCP 链路。宿主侧证据与自动化
回归套件分开记录。

## Repository checks

```text
python -m pytest -q
passed

python -m compileall -q src tests
passed

ruff check src\ainative tests
passed

python integrity_gate.py --json
ok: true
```

## Current execution safeguards

- The runtime has no built-in prompt router and selects no call for the Agent. The
  Agent supplies the task and owns every decision about what to call next.
- The runtime executes nothing. A plan is validated structurally only: there is no
  execution binding, no provider list, and no per-run provider check.
- MCP calls are first-class plan entries. A call carries `kind` (`mcp` or
  `project_tool`) and a `target` of owner/name, so a host call such as
  `{"owner": "ue5", "name": "set_actor_transform"}` participates in the call graph
  and in dependency ordering instead of being pushed into a `manual` check.
- A submitted result must match its declared call: an undeclared `call_id`, or a
  `kind`/`target` that disagrees with the Workflow, is rejected before it is recorded.
- Missing call arguments fail closed before execution. Malformed statuses and
  invalid CLI JSON fail closed before results are recorded.

## Call execution

```text
MCP call
    → kind=mcp, target: owner/name
    → Agent MCP Client → Blender MCP / UE5 MCP / ComfyUI MCP
```

There is no execution binding, no Tool registry, and no discovery index: the
plan's `target` names what the Agent will invoke, and the Agent's own MCP client
resolves and runs it. This repository ships no executable Toolset.

## 自动化覆盖

```text
ToolCall 必须带 call_id 与含 owner/name 的 target
MCP 调用（kind=mcp）作为计划的正式成员进入调用图
调用结果的 call_id 必须已在计划中声明
调用结果的 kind / target 与计划不一致 → 拒绝记录
required Stage 必须声明 execution/acceptance checklists
Stage call 依赖在执行前校验
真实提交的 MCP 调用结果通过 record 记录，并参与 tool_succeeded 等自动判据
调用成功不完成 Stage，除非有验收证据
manual/complex check 在 CheckResult 记录前保持 unknown
结构化读回相等可确定性完成 Stage
warning-only required checks → degraded Stage/Task
required fail/unknown/needs_human → 阻塞结果
Agent 不能覆盖确定性 check 或调用支撑的执行证据
checklist summaries 持久化在 StageResult
```

## Ownership model

```text
Skill 提示资产            → SKILL.md + guidance/ + references/
Agent                   → 决定做什么、按什么顺序、调用哪一个，并亲自执行
ToolCall contract       → 声明 call_id / kind / target / arguments / depends_on
StageAcceptanceEvaluator→ 产生 ExecutionItemResult / CheckResult / summaries
Acceptance session      → 记录 StageResult 并暴露下一步边界
```

宿主编辑器不由本仓库拥有：没有可执行文件路径、没有编辑器子进程、没有宿主插件。
本仓库也不执行任何调用——执行全部由 Agent 自己的 MCP Client 完成。

每个 Stage 由 Agent 按 Stage kind、处理对象、操作类型与当前事实组合，并在
副作用前冻结 execution / acceptance checklist。本仓库不附带分层知识库，也不附带
配方包；领域能力由 Agent 自己提供。

## Host MCP evidence

宿主能力经 MCP 到达，下列 live transport 证据仍然有效。

### Live UE5 MCP transport

2026-09-06 在仓库外的 UE5.8.2 测试项目中验证了原生 UE5 MCP 链路：

```text
ModelContextProtocol + AllToolsets mounted
MCP endpoint: 127.0.0.1:8000/mcp
initialize: passed
tools/list: passed
Toolset discovery: passed
```

这项验证证明了引擎插件、目标项目、Editor 进程和 Agent MCP Client 之间的 live
transport。

### ComfyUI MCP live transport

2026-09-06 在本机 ComfyUI 发行版环境中验证了完整的 ComfyUI MCP 链路：

```text
ComfyUI root: D:\work\Comfyui\ComfyUI-aki-v3.2
ComfyUI workspace: D:\work\Comfyui\ComfyUI-aki-v3.2\ComfyUI
ComfyUI core: v0.30.2
comfy-cli: 1.18.0
comfy-mcp: 0.10.0
MCP transport: stdio
MCP initialize: passed
tools/list: passed (39 tools)
ComfyUI API: http://127.0.0.1:8188
server_info: passed
system_stats: passed
workflow validation: passed
partner nodes: none
spends credits: false
run_workflow: queued -> completed
job wait: completed
fetch_outputs: passed
output bytes: 220156
```

端到端调用使用的是 `comfy-mcp` 暴露的 `run_workflow`、`job` 和 `fetch_outputs`，不是
绕过 MCP 的直接 HTTP 调用。验证文件和结果位于：

```text
artifacts/evidence/comfyui-mcp-live/minimal_sd15_v2.json
artifacts/evidence/comfyui-mcp-live/verification.json
artifacts/evidence/comfyui-mcp-live/outputs/c0bbe705_000.png
```

这项验证证明了：

```text
Codex MCP 配置
  → comfy-mcp（stdio）
  → comfy-cli
  → ComfyUI HTTP API :8188
  → RTX 2070 本地 GPU workflow
  → output PNG
```

验证过程中还发现，当前 gallery 的 `generate_image(checkpoint=...)` 快速入口默认模板
不一定暴露 checkpoint slot；指定 `DreamShaper_8_pruned.safetensors` 时应使用包含
`CheckpointLoaderSimple` 的 API workflow，再通过 `run_workflow` 执行。

## Hugging Face CLI / MCP integration

2026-09-06 已完成 Hugging Face 两条接入面的配置检查：

```text
Hugging Face MCP server: hf-mcp-server
MCP endpoint: https://huggingface.co/mcp?login
Codex status: enabled
Codex auth: OAuth
Hugging Face CLI: hf 1.19.0
CLI auth: not configured (`hf auth whoami` reports Not logged in)
```

HF MCP 可以用于 Hub 资源搜索和模型研究；本地 gated 模型下载仍需要在用户自己的终端
完成 `hf auth login`，再用 `hf download` 写入 ComfyUI 的模型目录。Token 不进入项目。
详细契约见 `docs/DEPENDENCIES.md`（Hugging Face 节）。
