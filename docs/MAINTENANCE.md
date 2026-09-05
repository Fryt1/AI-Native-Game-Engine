# Maintenance Guide

**Status:** Living maintainer guide（`docs/` 精简版；详细历史归档在 `artifacts/archive/docs/`）

## 架构不变量

```text
Task Contract
    → Route / Workflow guidance
    → 分层 Stage 知识
    → Agent 生成 WorkflowPlan
    → 冻结 execution + acceptance checklists
    → 精确 ToolCall / McpCall 可行性
    → 一次一个选定调用
    → ExecutionResult / CheckResult / StageResult / Evidence
```

- Agent 拥有 Steps、Stages、checklists、calls、参数与顺序。
- 每个 required Stage 都有 execution 与 acceptance checklist。
- 每个 Stage call 至少支撑一个 checklist 项。
- change Stage 在副作用前冻结 checklists 与必需 calls。
- Tool/MCP 成功不等于 Stage 语义完成。
- 需要证据的 required pass/warn 必须有证据引用。
- Stage 聚合是确定性的。
- 复杂比较是普通 Project Tool，不引入第二个 checker Registry。
- MCP Server 配置给 Agent；项目只定义 `McpCall` 契约，不带 MCP Client Runtime/Gateway。
- 不静默替换 Tool/MCP Server/Backend/Provider/丢失策略。
- 不重新引入 Capability / Python plan 生成 / 每运行快照。

## 知识维护

```text
knowledge/stage-kinds/   仅当 Stage 执行/验收行为不同
knowledge/objects/       仅当对象暴露不同事实或保留要求
knowledge/operations/    仅当操作需要不同执行/证明规则
```

不要为每个 host/object/operation 组合维护 recipe。

## Workflow Definition 维护

```text
workflows/<workflow-id>/
```

流程：

```text
create draft（artifacts/scratch/workflow-drafts/）
    → 校验 plan template 与 requirements
    → 在 projects/fixtures/ 上运行
    → 机器验证（artifacts/evidence/）
    → 需要时人工评审
    → promote 到 workflows/
```

一个 Workflow Definition 可同时引用 Project Tool ID 与 MCP server/tool 对。

## 恢复语义

```text
Tool/MCP 失败      → 重试该精确调用，或运行显式补偿 Tool
required unknown   → 补证据；否则 blocked 并报告缺什么
needs_human        → 等待决策
计划/清单错误       → 作废该 revision，由 Agent 重写替换版
```

失败时不得删除 acceptance 项。计划作废不撤销外部 UE5/Blender/文件系统状态。

## 变更归属速查

| 变更 | 权威 owner | 同步更新 |
|---|---|---|
| Route | `skills/.../workflows/routing.md`、`src/ainative/orchestration/contracts/task.py` | route guards、tests |
| Workflow guidance | `skills/.../workflows/*.md` | examples、tests |
| 已发布 Workflow | `workflows/<workflow-id>/` | requirements、verification、fixtures |
| Stage-kind 行为 | `skills/.../knowledge/stage-kinds/` | template、acceptance tests |
| 对象事实 | `skills/.../knowledge/objects/` | Stage examples |
| 操作规则 | `skills/.../knowledge/operations/` | Stage examples |
| 计划/调用格式 | `skills/.../templates/`、`src/ainative/orchestration/contracts/` | integrity gate、tests |
| Project Tool | `src/ainative/toolsets/<unit>/` + `skills/.../toolsets/<unit>/TOOLSET.md` | Registry tests、E2E |
| Project Registry | `src/ainative/registry/` | Registry tests |
| MCP 契约 | `src/ainative/orchestration/contracts/tools.py` + Agent MCP 配置 | McpCall/result tests、Agent docs |
| Plan 校验 | `src/ainative/orchestration/planning/lifecycle.py` | contract tests |
| Stage 验收 | `src/ainative/orchestration/acceptance/evaluator.py` | acceptance tests |
| Agent Session | `src/ainative/agent/` | integration tests |
| 稳定证据 | `artifacts/evidence/` | `docs/VALIDATION_REPORT.md` |

## 验证命令

```powershell
python -m pytest -q
python skills\ai-native-workflow-orchestration\scripts\integrity_gate.py --json
python -m compileall -q src scripts skills tests
ruff check src\ainative scripts\e2e scripts\agent scripts\docs scripts\workflows tests
```

## 新增文档规则

新建文档前回答：

```text
谁读它？
它拥有什么事实？
现在哪个文档拥有该事实？
运行时要加载它吗？
```

只给维护者看的清单/历史不进运行时加载，放 `artifacts/archive/`。


## 目录维护规则（来自原 PROJECT_STRUCTURE）

- 项目 Tool 变更：更新实现 + `skills/.../toolsets/<unit>/TOOLSET.md` + 测试 + 依赖它的 Workflow Definition。
- MCP 行为变更：更新 Agent MCP 配置 + `McpCall` 契约 + 校验契约（项目不拥有 MCP Client）。
- WorkflowPlan 语义变更：更新契约 + Skill 模板/schema + 架构文档（`docs/FINAL_ARCHITECTURE.md`）+ fixtures。
- 历史/过程文档一律放 `artifacts/archive/`，不重新进入 `docs/`。
