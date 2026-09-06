# Validation Report

> Latest validation: September 6, 2026（直接 MCP 调用、live UE5 MCP transport、ComfyUI MCP process handshake、workflow-backed Tools、可复用 Workflow Definition 生命周期）。
> 本文件是 `docs/` 精简版；旧版全文归档在 `artifacts/archive/docs/VALIDATION_REPORT.md`。

## Scope

记录最终两路径执行模型的仓库验证：Project `ToolCall`、直接 `McpCall`、
WorkflowPlan 生成与结构化验收。既有 UE5 证据与自动化回归套件分开记录。

## Repository checks

```text
python -m pytest -q
75 passed

python -m compileall -q src scripts skills tests
passed

ruff check src\ainative scripts\e2e scripts\agent scripts\docs scripts\workflows tests
passed

python skills\ai-native-workflow-orchestration\scripts\integrity_gate.py --json
ok: true（含 toolsets/*/TOOLSET.md 契约）

python scripts\workflows\validate_workflow.py workflows\blender-ue5-asset-roundtrip --json
ok: true

python scripts\e2e\ue5\run_actor_operation_e2e.py --timeout 120
passed（真实 UE5.7.1：Actor 读取、Transform 修改、保存、读回；可见 Editor
窗口证据已记录，测试 harness 的主动清理可能产生预期的非零进程码）

BLENDER_EXECUTABLE=E:\blender\blender.exe python -m pytest -q
tests\integration\blender\test_cli.py tests\integration\transfer\test_direct_workflow_real_blender.py
tests\integration\transfer\test_full_bridge_workflow.py
passed（真实 Blender 5.2.1 LTS：CLI create/modify/export/import/inspect、
Direct Transfer、AssetsBridge JSON round-trip）

workflow create → validate → promote smoke lifecycle
passed（发布产物 smoke 后已清理）

WorkflowPlan template JSON / JSON Schema / SVG XML parse
passed
```

## Current execution safeguards

- The runtime has no built-in prompt router. The Agent supplies the TaskContract
  and owns Route/Workflow judgment; the runtime never selects an exact Project
  Tool or MCP Tool. An explicitly injected Agent/LLM interpreter is optional.
- WorkflowPlan runtime dimensions must match the selected Route/Workflow,
  including authority, host, Backend, call surface, and modification method.
- Superseded, completed, failed, or invalid plan revisions cannot be started.
- CLI task loading derives the same selection context used by the Agent, so
  Direct Transfer receives its Backend context instead of silently skipping the
  Blender import/export seam. AssetsBridge tasks receive an isolated per-task
  exchange directory.
- AssetsBridge JSON writes are atomic and carry a transfer identity when the
  protocol owns the document. Validators compare source/result snapshots rather
  than treating field presence as proof of preservation.
- Host process result files are cleared before execution and malformed statuses,
  stale result IDs, invalid CLI JSON, missing Tool arguments/outputs, and process
  timeouts fail closed.

## WorkflowGuide / CLI 架构

本轮把 `AgentHost`/`AgentExecutionSession` 改名为 `WorkflowGuide`/`WorkflowSession`，
并从校验 Session 中移除 Python 侧 Tool 执行：

```text
WorkflowGuide.start(task, plan, runtime)
    → 校验 plan 结构与 Project Tool 可行性
    → 返回 WorkflowSession

Agent 执行 Tools/MCP
    → session.record_execution_result(ExecutionResult)

session.complete_stage(stage_id)
    → 确定性 Stage 验收

session.finish()
    → WorkflowResult
```

Project Tool 另有进程 CLI（`python -m ainative.tools ...`）供 Agent 直接执行：
解析 Registry 中确切 Tool、执行实现、输出结构化 `ExecutionResult`。

## 自动化覆盖

```text
Project ToolCall 只经 Project Tool Registry 解析
McpCall 契约由 Python 在 Agent MCP Client 执行后校验
MCP target 与结构化 result shape 校验；远端 schema/可用性仍由 Agent MCP Client 负责
Stage 中 McpCall 可与 Project ToolCall 并列
MCP 结构化输出参与确定性验收
Python-script-backed Workflow Tools 发布为普通 Project Tools
required Stage 必须声明 execution/acceptance checklists
Stage call 依赖在执行前校验
Tool/MCP 成功不完成 Stage，除非有验收证据
manual/complex check 在 CheckResult 记录前保持 unknown
结构化读回相等可确定性完成 Stage
warning-only required checks → degraded Stage/Task
required fail/unknown/needs_human → 阻塞结果
Agent 不能覆盖确定性 check 或 Tool-backed 执行证据
checklist summaries 持久化在 StageResult
```

## Ownership model

```text
Workflow Definition  → 可复用指导/需求/plan template/验证记录
Agent                → 实例化具体 WorkflowPlan 并选择调用顺序
Project Tool Registry→ 发现并精确解析自有 ToolCall
Agent MCP Client（外部 Codex 配置）→ 连接 MCP Server 并执行精确 McpCall
Tool implementation  → 返回 TaskResult，规范化为 ExecutionResult + Evidence
StageAcceptanceEvaluator → 产生 ExecutionItemResult / CheckResult / summaries
WorkflowSession      → 记录 StageResult 并暴露下一步边界
```

只有一个 Project Tool Registry；MCP Tools 不复制进来；项目没有第二个 MCP
Client Runtime，也没有第二个 checker Registry。

## Workflow Definition lifecycle

```text
workflows/blender-ue5-asset-roundtrip/
    WORKFLOW.md / plan.template.yaml / requirements.yaml / examples/ / tests/ / verification/
```

```text
scripts/workflows/create_workflow.py
scripts/workflows/validate_workflow.py
scripts/workflows/promote_workflow.py
```

Promote 需要机器报告 `status=passed`，且人工评审 `status=approved` 或
`status=not_required`。

## Existing host evidence

此前 UE5.7.1 证据保留在：

```text
artifacts/evidence/ue5-host-operation/
artifacts/evidence/ue5-level-template/
artifacts/evidence/blender-ue5-roundtrip/
```

已验证 UE5 操作：

```text
Actor 读取 / Transform 修改 / 保存 / 读回
从 /Engine/Maps/Templates/Template_Default 创建关卡
DirectionalLight / SkyLight 读回
AssetsBridge export/import
```

**UE5 native MCP live transport 已验证**；但仓库 fixture 仍未默认启动常驻 MCP Editor，且
仍需要真实 Blender MCP host 运行，才能把 Blender MCP 路径升级为 live MCP evidence。自动化
MCP 测试目前用确定性 fake session 验证契约，不是真实编辑器。
项目自己的 Blender CLI / Direct Transfer / AssetsBridge JSON 真实宿主路径
已在本机 Blender 5.2.1 上验证通过。

## Live UE5 MCP transport

2026-09-06 在仓库外的 UE5.8.2 测试项目中验证了原生 UE5 MCP 链路：

```text
ModelContextProtocol + AllToolsets mounted
MCP endpoint: 127.0.0.1:8000/mcp
initialize: passed
tools/list: passed
Toolset discovery: passed
```

这项验证证明了引擎插件、目标项目、Editor 进程和 Agent MCP Client 之间的 live
transport。它不等于仓库 fixture 已经变成常驻 MCP Editor；fixture 的 Project Tool
执行面与 live MCP 执行面仍然分开维护。

## ComfyUI MCP live transport

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
完成 `hf auth login`，再用 `hf download` 写入 ComfyUI 的模型目录。Token 不进入项目
详细契约见 `docs/DEPENDENCIES.md`（Hugging Face 节）。
