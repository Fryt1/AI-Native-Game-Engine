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
  Agent 用自己的 MCP client 确认目标 MCP Server 正在运行。

## 指引维护

```text
templates/*.md           形状与写法：Workflow schema、结果契约
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
| 计划/清单格式 | `src/ainative/model/tree.py` | `templates/workflow.schema.json`、integrity gate、tests |
| 调用契约（`ToolCall` / `CallTarget`） | `src/ainative/model/tools.py` | deserialize、contract tests |
| 提交结果的形状 | `templates/result-contract.md` | `docs/cli.md`、deserialize、contract tests |
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
ruff check src/ainative tests
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

**然后按它定义的是什么决定去向**——四问只筛掉重复，落点看这张表：

| 它定义的是 | 放哪 | 判据 |
|---|---|---|
| 引擎校验的形状 | `templates/` | `open` 真的读它。spec 与它校验的数据是一对 |
| Agent 提交上来的形状 | `templates/` | 契约的另一半，同上。结果文档目前没有 schema，但归这里 |
| 上面两种怎么写 | `templates/` | 模板就是"写的规则" |
| 引擎内部机制 | `docs/` | 只有维护者读 |
| 仓库级规矩 | `AGENTS.md` | 第一份，永远 |
| 跑过的证据 | `docs/VALIDATION_REPORT.md`、`artifacts/` | 历史，不是规则 |

**没有落点的情况要警惕。** 一份文档如果落不进任何一格，通常说明它要定义的事实**不在本仓库**——例如"某个宿主能调哪些调用"，答案由运行中的 MCP Server 决定。此时正确做法是从运行时加载顺序里删掉它，而不是为它新建一个目录。

`references/` 就是这样消失的：它装的两类事实，一类（提交结果的形状）归 `templates/`，另一类（宿主能调什么）不在本仓库。

### 落点决定位置，但不决定是否随包发出

上面这张表说的是文档**住哪**。打包另有一问：**它要不要跟着 skill 走**。

`install_skill.py` 只装"驱动引擎"需要的东西，不装"开发引擎"需要的东西。判据是**加载顺序**：`SKILL.md` 第 2–5 步真正点到的文件才进包。`AGENTS.md`、`README.md`、`docs/ARCHITECTURE.md`、`docs/MAINTENANCE.md`、`docs/VALIDATION_REPORT.md` 都住在本仓库、都被维护者读，但没有一个在加载顺序里——它们进的是 `DEVELOPMENT_ONLY` 清单，每条带一句理由。

新增一份顶层文档时，必须二选一：进 `BUNDLE_FILES`，或进 `DEVELOPMENT_ONLY`。两个测试分别把守两个方向：漏选会被 `test_every_top_level_document_is_bundled_or_declared_development_only` 拦下，多装会被 `test_every_bundled_document_is_one_the_body_reaches` 拦下——后者防的是把 ARCHITECTURE.md 之类发给只使用引擎的人。

`docs/` 在包里是**文件清单而不是目录**：加载顺序只到 `cli.md` 一份，写成目录会把其余几份一起拖进去。

## 目录维护规则

- 调用契约变更：更新 `model/tools.py` + deserialize + fixtures。
- 宿主 MCP 行为变更：本仓库不拥有 MCP
  Client，也不代 Agent 做前置检查）。
- 计划语义变更：更新契约 + 架构文档（`docs/ARCHITECTURE.md`）+ fixtures。
- 新增/删除提示资产：同步 `docs/` 各文件中的目录树，以及 `integrity_gate.py`
  的 required 列表。
