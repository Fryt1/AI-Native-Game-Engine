# Maintenance Guide

**Status:** Living maintainer guide

## 架构不变量

```text
Task Contract
    → Agent 按 Stage kind + 对象 + 操作 + 当前事实组合
    → Agent 决定这次做什么
    → 冻结 execution + acceptance checklists
    → 一次一个选定调用
    → ExecutionResult / CheckResult / StageResult / Evidence
```

- Agent 拥有 Stages、checklists、调用、参数与顺序。
- 每个 required Stage 都有 execution 与 acceptance checklist。
- 每个 Stage call 至少支撑一个 checklist 项。
- change Stage 在副作用前冻结 checklists 与必需调用。
- Tool/MCP 成功不等于 Stage 语义完成。
- 需要证据的 required pass/warn 必须有证据引用。
- Stage 聚合是确定性的。
- MCP Server 配置给 Agent；本仓库不带 MCP Client Runtime/Gateway。
- 不静默替换 MCP Server/Target/Backend/丢失策略。
- 不重新引入 Capability、Tool registry、执行绑定、provider 列表、Python Workflow
  生成或每运行快照。

## 宿主软件边界

**Blender 和 UE5 通过它们自己的 MCP Server 由 Agent 调用。** 本仓库不持有它们的
可执行文件路径、不启动编辑器进程、不打包宿主插件。

- 需要新的宿主能力时，加在宿主侧的 MCP Server 里，不加在这里。
- 本仓库留下的是没有宿主依赖的部分：跨宿主传输的文件协议、校验、验收引擎。
- 依赖版本与前置条件写在 `docs/DEPENDENCIES.md`；
  Agent 用自己的 MCP client 确认目标 MCP Server 正在运行。

## 指引维护

```text
guidance/*.md            仅当一条宏观生命周期的执行/验收行为不同
references/*.md          说明宿主如何接入（本仓库不含可执行 Toolset）
```

不要为每个 host/object/operation 组合维护单独文档。Agent 按 `SKILL.md` 的组合
规则（Stage kind + 处理对象 + 操作类型 + 当前事实 + 用户要求）现场组合每个 Stage，
领域能力由 Agent 自己提供——本仓库不维护对象/操作知识库，也不维护配方包。

## 恢复语义

```text
Tool/MCP 失败      → 重试该精确调用，或运行显式补偿 Tool
required unknown   → 补证据；否则 blocked 并报告缺什么
needs_human        → 等待决策
计划/清单错误       → 由 Agent 写替换版
```

失败时不得删除 acceptance 项。计划作废不撤销外部 UE5/Blender/文件系统状态。

## 变更归属速查

| 变更 | 权威 owner | 同步更新 |
|---|---|---|
| 生命周期指引 | `guidance/*.md` | `guidance/index.md`、integrity gate、examples |
| 计划/清单格式 | `src/ainative/model/tree.py` | `templates/workflow.schema.json`、integrity gate、tests |
| 调用契约（`ToolCall` / `CallTarget`） | `src/ainative/model/tools.py` | deserialize、contract tests |
| 宿主接入说明 | `references/*.md` | README、`docs/DEPENDENCIES.md` |
| Host/MCP dependency policy | `docs/DEPENDENCIES.md` | README、live handshake evidence |
| Model acquisition policy | `docs/DEPENDENCIES.md`（Hugging Face 节） | CLI auth/download evidence、model revision/hash、license review |
| Workflow 形状 spec | `templates/workflow.schema.json` | `src/ainative/reading/schema.py`、`test_schema_agreement.py` |
| Workflow 语义校验 | `src/ainative/reading/tree_validate.py` | contract tests、`test_schema_agreement.py` |
| Node 验收 | `src/ainative/acceptance/evaluator.py`、`tree_evaluator.py` | acceptance tests |
| Agent Session | `src/ainative/session_api/` | integration tests |
| 稳定证据 | `artifacts/evidence/` | `docs/VALIDATION_REPORT.md` |

## 验证命令

```powershell
python -m pytest -q
python integrity_gate.py --json
python -m compileall -q src tests
ruff check src\ainative tests
```

## 新增文档规则

新建文档前回答：

```text
谁读它？
它拥有什么事实？
现在哪个文档拥有该事实？
运行时要加载它吗？
```

只给维护者看的清单不进运行时加载。

## 目录维护规则

- 调用契约变更：更新 `model/tools.py` + deserialize + fixtures。
- 宿主 MCP 行为变更：更新 `docs/DEPENDENCIES.md` 对应小节（本仓库不拥有 MCP
  Client，也不代 Agent 做前置检查）。
- 计划语义变更：更新契约 + 架构文档（`docs/ARCHITECTURE.md`）+ fixtures。
- 新增/删除提示资产：同步 `guidance/index.md`、`docs/` 各文件中的目录树，
  以及 `integrity_gate.py` 的 required 列表。
