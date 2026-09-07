# AI Native Game Engine 最终架构

> 版本：2026-09-05（docs 精简版；完整历史归档在 `artifacts/archive/docs/`）

## 一句话结论

**Agent 读取项目上下文并生成 WorkflowPlan，Agent 直接调用 MCP Server 或项目 Tool；Python 不替 Agent 调用工具，只负责校验结构化计划和结果、执行确定性 Stage/Workflow 验收。**

## 总体结构

```text
Codex / Agent
    ↓
项目上下文
    ├── AGENTS.md
    ├── Skill（skills/ai-native-workflow-orchestration/）
    ├── knowledge/
    ├── workflows/<workflow-id>/WORKFLOW.md
    └── plan.template.yaml
    ↓
Agent 生成 WorkflowPlan
    ├── Step
    │   └── Stage
    │       ├── execution_checklist[]
    │       ├── acceptance_checklist[]
    │       └── calls[]
    │           ├── ToolCall
    │           └── McpCall
    ↓
Python 校验 WorkflowPlan
    ↓
Agent 直接调用真实能力
    ├── MCP Tool（Blender MCP / UE5 MCP / ComfyUI MCP）
    └── Project Tool（Tool Registry 中我们自己维护的 Tool）
    ↓
原始 Tool/MCP Result
    ↓
Python 校验并规范化为 ExecutionResult
    ↓
StageAcceptanceEvaluator
    ↓
StageResult
    ↓
Agent 继续 / 重试 / 补证据 / 人工确认 / 重新规划
    ↓
WorkflowResult
```

## 两条执行路径

```text
ToolCall
    → Project Tool Registry
    → AssetsBridge / Validation / script-backed / ComfyUI Tools

McpCall
    → Agent MCP Client
    → Blender MCP / UE5 MCP
```

- MCP Server 直接配置给 Agent（如 Codex），项目不把 MCP Tool 镜像进自己的
  Tool Registry，也不做 MCP Gateway/Client Runtime。
- 项目自有的 Blender/UE5 脚本、ComfyUI 图可以作为普通 Project Tool；外部 ComfyUI MCP
  使用直接 McpCall；它们都不是第三种调用类型。
- 每条调用都可带 `usage: execute|observe|verify|report`，只记录本次用途。

## Project Tool Registry

```text
Tool Registry
    └── Toolset
        └── Tool
```

典型 Tool：

```text
transfer.assetsbridge.transfer_to_edit_host
transfer.direct.export_source
validation.workflow.validate
blender.workflow.prepare_unreal_asset
ue5.workflow.create_default_level
comfy.workflow.generate_material_texture
```

## Workflow Definition 与 WorkflowPlan

- **Workflow Definition**：`workflows/<workflow-id>/`（`WORKFLOW.md`、
  `plan.template.yaml`、`requirements.yaml`、`examples/`、`tests/`、
  `verification/`）。描述适用场景、不变量、允许调用、阶段建议、风险恢复和
  验收方法；不是固定脚本。
- **WorkflowPlan**：Agent 针对当前任务生成的具体计划；`calls[]` 只有
  `tool` 与 `mcp` 两种。
- Python 只做结构校验、关系校验、运行结果校验和语义验收，不生成/重排计划，
  不决定下一步。

## 验收模型

每类结果：`pass | warn | fail | unknown | needs_human`。

```text
required fail        → failed
required unknown     → blocked
required needs_human → needs_approval
required warn only   → degraded
all required pass    → succeeded
```

复杂语义验收必须通过读回 Tool/MCP、文件证据或人工审核，不能只靠 Agent 自然
语言总结。每个 Stage 在副作用前冻结 `execution_checklist` 与
`acceptance_checklist`。

## 关键文档位置

| 内容 | 位置 |
|---|---|
| 仓库级 Agent 规则 | `AGENTS.md` |
| Skill 契约与执行纪律 | `skills/ai-native-workflow-orchestration/SKILL.md` |
| 分层知识 | `skills/ai-native-workflow-orchestration/knowledge/` |
| 计划/清单稳定格式 | `skills/ai-native-workflow-orchestration/templates/` |
| Toolset 契约 | `skills/ai-native-workflow-orchestration/toolsets/` |
| 可复用工作流定义 | `workflows/` |
| 架构流程导览（新用户） | `docs/ARCHITECTURE_GUIDE.md` |
| 新增可复用工作流指南 | `docs/ADDING_A_WORKFLOW.md` |
| 维护与目录规则 | `MAINTENANCE.md` |
| 验证证据 | `VALIDATION_REPORT.md` |
| 历史决策与旧版 | `artifacts/archive/docs/` |

## 演进历史（摘要）

```text
Route Families 作为护栏
    → Workflow-first 计划组合
    → 泛化 Skill 边界
    → 目录/证据布局清理
    → Toolset Registry 替代 Capability Binding
    → Agent 拥有 WorkflowPlan 与逐调用执行
    → 动态 Stage 的执行/验收清单
    → 直接 MCP 与 Project Tool 双路径
```

详细 ADR 与过程文档全部归档在 `artifacts/archive/docs/`，仅保留以上结论。
