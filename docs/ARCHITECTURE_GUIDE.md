# Architecture Guide: How the Pieces Fit Together

> 面向读者：新用户 / 贡献者。想快速理解本项目的模块分工、一次任务从请求到落地
> 如何流转，以及每类资产/文档放哪里。详细维护规则见 `docs/MAINTENANCE.md`，
> 依赖契约见 `docs/DEPENDENCIES.md`，Agent 执行纪律见 `AGENTS.md`。

## 1. 总体流程

```text
用户/Agent 意图
    → TaskContract（规范化输入）
    → Route 护栏（host_operation | asset_transfer | artifact_pipeline）
    → Workflow guidance（固定复用包，命中才读；不命中走通用动态）
    → 分层 Stage 知识（stage-kinds / objects / operations）
    → Agent 生成 WorkflowPlan
        └── Step → Stage
            ├── execution_checklist[]
            ├── acceptance_checklist[]
            └── calls[]  （ToolCall | McpCall）
    → 可行性 Gate（结构/依赖/调用可解析）
    → Agent 一次调用一个真实工具
        ├── Project Tool（Registry）
        └── MCP Tool（Blender/UE5/ComfyUI MCP）
    → ExecutionResult → CheckResult → StageResult
    → Agent 继续 / 重试 / 补证据 / 等人工 / 重新规划
```

## 2. 模块与职责边界

| 模块 | 是什么 | 负责 | 不负责 |
|---|---|---|---|
| Agent | 编排者（Codex 等） | 读上下文、选 Route/Workflow、生成 WorkflowPlan、逐个调用、判断下一步 | 不把决定权交给 Python |
| Python runtime | 本项目代码 | 校验 plan 结构、解析 Tool/MCP、确定性验收、记录结果 | 不生成/重排 plan，不调度 |
| Project Tool Registry | `src/ainative/registry/` | 管理项目自有 Tool（Toolset→Tool） | 不镜像 MCP Tool |
| MCP Client | 配置给 Agent 的外部客户端 | 执行 Blender/UE5/ComfyUI 等 MCP 调用 | 项目不持有它 |
| Skill 包 | `skills/ai-native-workflow-orchestration/` | 给 Agent 的分层知识与模板 | 不是运行时调度器 |
| Workflow 包 | `workflows/<id>/` | 固定复用的 Definition（guidance + requirements + plan.template） | 不是固定脚本 |

## 3. 三种 Route（生命周期护栏）

Route 选的是“这次任务的主要状态变化路径”，不是工具，也不是某个固定 Workflow。

```text
host_operation     状态在单一宿主内变化（读状态→改→保存→读回验证）
asset_transfer     资产跨宿主边界移动/往返（Transfer Manifest、保留关系、损失策略）
artifact_pipeline  外部产物生成→应用/发布（产物来源、格式约束、应用证据）
```

一个请求含多个生命周期时，**切成多个 Workflow 实例顺序执行**，用
Artifact/Transfer Contract 传递，不发明组合 Route。

## 4. 三个容易混的概念

```text
Workflow Definition（固定复用）
    workflows/<id>/{WORKFLOW.md, requirements.yaml, plan.template.yaml}
    = 指导 + 依赖 + 可实例化骨架；无 plan_id/revision/status

WorkflowPlan（每次任务生成）
    = 把 plan.template 填实 + plan_id/revision/status + 具体 calls/checklists
    = 有生命周期状态：draft → feasible → running → completed/failed/superseded

Graph / Script（执行体）
    = 真正被调用的实现（ComfyUI JSON、Blender .py）
    = 注册为 Project Tool，放在 src/ainative/toolsets/<id>/ 下
```

## 5. 两条执行路径

```text
ToolCall  → Project Tool Registry
            → AssetsBridge / Validation / script-backed / ComfyUI Tools

McpCall   → Agent MCP Client
            → Blender MCP / UE5 MCP / ComfyUI MCP
```

调用都可带 `usage: execute|observe|verify|report`（只描述本次用途）。

## 6. 验收与证据

每类结果：`pass | warn | fail | unknown | needs_human`

```text
required fail        → failed
required unknown     → blocked
required needs_human → needs_approval
required warn only   → degraded
all required pass    → succeeded
```

关键规则：

- 每个 required Stage 在副作用前冻结 execution + acceptance checklist；
- Tool/MCP 返回成功 ≠ Stage 语义完成，需要读回/文件/人工证据；
- 需要证据的 pass/warn 必须有证据引用。

## 7. 资产/文档地图

```text
仓库级 Agent 规则          AGENTS.md
架构结论（精简）            docs/FINAL_ARCHITECTURE.md
本导览                     docs/ARCHITECTURE_GUIDE.md
新增可复用流程指南          docs/ADDING_A_WORKFLOW.md
维护规则                    docs/MAINTENANCE.md
依赖契约                    docs/DEPENDENCIES.md
Skill 契约                  skills/ai-native-workflow-orchestration/SKILL.md
分层知识                    skills/ai-native-workflow-orchestration/knowledge/
稳定模板                    skills/ai-native-workflow-orchestration/templates/
Toolset 契约                skills/ai-native-workflow-orchestration/toolsets/
已发布 Workflow             workflows/
项目 Toolset                src/ainative/toolsets/
验证证据                    artifacts/evidence/
历史决策/过程                artifacts/archive/docs/
```