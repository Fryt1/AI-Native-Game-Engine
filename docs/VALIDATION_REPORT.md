# Validation Report

> Latest validation: September 5, 2026（直接 MCP 调用、workflow-backed Tools、可复用 Workflow Definition 生命周期）。
> 本文件是 `docs/` 精简版；旧版全文归档在 `artifacts/archive/docs/VALIDATION_REPORT.md`。

## Scope

记录最终两路径执行模型的仓库验证：Project `ToolCall`、直接 `McpCall`、
WorkflowPlan 生成与结构化验收。既有 UE5 证据与自动化回归套件分开记录。

## Repository checks

```text
python -m pytest -q
57 passed

python -m compileall -q src scripts skills tests
passed

ruff check src\ainative scripts\e2e scripts\agent scripts\docs scripts\workflows tests
passed

python skills\ai-native-workflow-orchestration\scripts\integrity_gate.py --json
ok: true（含 toolsets/*/TOOLSET.md 契约）

python scripts\workflows\validate_workflow.py workflows\blender-ue5-asset-roundtrip --json
ok: true

workflow create → validate → promote smoke lifecycle
passed（发布产物 smoke 后已清理）

WorkflowPlan template JSON / JSON Schema / SVG XML parse
passed
```

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
MCP target/schema/result 契约校验（执行仍是 Agent MCP Client 职责）
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

**仍需要一次真实 Blender MCP / UE5 MCP host 运行**，才能把这些路径升级为
live MCP evidence；自动化 MCP 测试目前用确定性 fake session 验证契约，不是真实编辑器。
