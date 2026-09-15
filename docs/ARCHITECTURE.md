# 架构与数据流

> 本文件回答两个问题：**系统由哪几层构成**、**一次任务是怎样的数据流**。
> 结论都取自实际代码，不是设计意图。

## 一、一句话架构

**Agent 决定做什么并亲自执行；Python 只做两件它不能委托的事——校验计划结构，和按 Agent 自己冻结的清单给出确定性判定。**

```
┌─────────────────────────────────────────────────────────────┐
│  Agent（Codex 等）                                          │
│  读指引 · 组合 Stage · 定计划 · 逐个调用 · 判断下一步       │
└───────────────────────────────┬─────────────────────────────┘
                                │ 全部调用：Agent 自己的 MCP client
                                ▼
                 ┌──────────────────────────────┐
                 │ Blender MCP Server           │
                 │ UE5 MCP Server               │
                 │ ComfyUI MCP Server           │
                 └──────────────┬───────────────┘
                                │ 结果交回
                                ▼
                 ┌──────────────────────────────┐
                 │ ainative.session             │
                 │  存证据 · 按冻结清单判定        │
                 └──────────────────────────────┘
```

**本仓库不持有任何宿主软件，也不执行任何调用。** 没有 Blender/UE5 可执行文件路径、
没有编辑器子进程、没有宿主插件、没有执行绑定、没有 provider 列表。留下的只有无宿主
依赖的部分：清单契约、结构校验、验收引擎。

## 二、分层与职责

| 层 | 位置 | 拥有什么 | 不做什么 |
|---|---|---|---|
| Skill 文档 | 仓库根：`SKILL.md`、`guidance/`、`references/` | 生命周期指引、宿主接入说明 | 不是运行时 |
| 模型层 | `model/` | 数据结构（纯 dataclass） | 无行为 |
| 读取层 | `reading/` | 读 JSON、校验计划结构 | 不生成计划、不排序、不解析调用目标 |
| 验收层 | `acceptance/` | 按清单确定性判定、确认门 | 不调用任何 Tool |
| 会话层 | `session_api/` | 加载 Skill、记录证据、关闭 Stage、汇总 | 不选择、不执行调用 |
| 入口 | `cli/commands.py` | 唯一的进程级 CLI | — |

### 关键分层原则

**模型层是纯数据。** `model/` 下全是 `@dataclass(frozen=True, slots=True)`，没有方法做决定，只有 `to_dict()` 和少量派生属性（如 `WorkflowPlan.stage_requests`）。

**验收层不认识 Tool。** `StageAcceptanceEvaluator.evaluate()` 只接收：一个 `StageRequest`、若干 `ExecutionResult`、以及 Agent 提交的清单结果。它不解析、不绑定、不执行。

## 三、数据结构

### 输入侧（Agent 写）

```
TaskContract                        这次任务"是什么"
├── task_id / objective
├── route                           host_operation | asset_transfer | artifact_pipeline
├── preserve_relations              必须存活的关系
├── source_context / target_context  从哪里到哪里
├── preferred_workflow_id            Agent 想读哪份指引（可选）
├── confirmation_required            是否需要先确认意图
└── metadata

ExecutionPlan
└── workflow: WorkflowPlan

WorkflowPlan                        一次计划修订
├── workflow_id / route
├── steps[]                         WorkflowStep
├── workflow_id / revision / status
├── supersedes_workflow_id / replacement_reason
└── recovery_pointer

WorkflowStep
├── step_id / purpose
├── stages[]                        StageRequest
└── depends_on / optional

StageRequest                        一个本地目标
├── stage_id / purpose / operation
├── stage_kind                      change | investigation | planning
├── execution_checklist[]           做什么，防漏
├── acceptance_checklist[]          证明什么，防"没报错就算过"
├── calls[]                         ToolCall
└── depends_on / required / recovery

ToolCall                             一次 Agent 声明的调用
├── call_id
├── target                          CallTarget：owner + name
├── arguments
└── depends_on
```

`target` 就是调用本身：`owner` 是 MCP server 名，`name` 是它上面的 tool 名。
本仓库解析不了它——解析并执行的是 Agent 自己的 MCP client。

### 证据与结果（流动中产生）

```
ExecutionResult                     一次调用的结果（Agent 提交）
├── call_id / status
├── target                          CallTarget | None
├── outputs                        自由字段
├── preserved_relations            一等证据
├── lost_relations                 一等证据
├── artifacts[]                    ArtifactRef
├── warnings / errors
└── resume_pointer

ExecutionItemResult                 一条执行清单项的结果
CheckResult                         一条验收项的结果
ChecklistSummary                    total/required/passed/warned/failed/unknown/needs_human

StageResult                         Stage 判定
├── stage_id / step_id / status
├── execution_results[]
├── execution_item_results[]
├── check_results[]
├── execution_summary / acceptance_summary
├── outputs / artifacts / warnings / errors
└── resume_pointer

TaskResult                          最终汇总
├── status / route / workflow_id
├── workflow_id / workflow_revision / workflow_revision_id / workflow_status
├── stages_completed[] / steps_completed[]
├── stage_results[]
├── preserved_relations / lost_relations
├── artifacts / details / warnings / errors
└── next_action / resume_pointer
```

## 四、数据流：一次完整任务

```
① Agent 读文档
   AGENTS.md → SKILL.md → 完整性门 → guidance/ → references/
   （需要宿主时读 docs/DEPENDENCIES.md）

② Agent 写 TaskContract（JSON）

③ Agent 写计划（JSON）
   为每个 required Stage 冻结两份清单

④ python -m ainative.session open --task --workflow
   ├── 读 JSON → 框架契约（workflow_from_dict）
   ├── 校验结构（validate_workflow_structure）
   │   ├── required Stage 必须冻结 execution/acceptance checklist
   │   ├── 每个 call 必须有 call_id 与含 owner/name 的 target
   │   └── depends_on 只能指向更早声明的 call / Stage / Step
   └── 写 state.json

⑤ Agent 执行（自己的 MCP client）
   一次一个调用，不静默替换目标

⑥ python -m ainative.session record --result <已执行调用的 JSON>
   ├── 校验 call_id 已在计划中声明
   ├── 校验 target 与计划一致
   └── 追加到有序事件日志，重放全部事件

⑦ python -m ainative.session stage --stage <id>
   └── StageAcceptanceEvaluator 判定

⑧ 按 StageResult 决定：继续 / 重试 / 等人工 / 补证据 / 换方案

⑨ python -m ainative.session finish
   └── 汇总 TaskResult
```

### 为什么状态是"有序事件日志"

每次 CLI 调用是独立进程，所以要落盘。但**顺序不能丢**：一个调用只有在其依赖的 Stage 关闭之后才允许记录。若用扁平列表回放，会重现已满足的依赖失败。

```json
{
  "version": 1,
  "task":  { ... },
  "workflow": { ... },
  "events": [
    {"type": "execution_result", "payload": { ... }},
    {"type": "stage_closed",      "payload": {"stage_id": "stage.first"}},
    {"type": "execution_result", "payload": { ... }},
    {"type": "stage_closed",      "payload": {"stage_id": "stage.second"}}
  ]
}
```

task 与 workflow 都存在状态里，所以 `open` 之后各命令不必重复传 `--task` / `--workflow`。
计划只做结构校验，不依赖任何本机 provider 配置，因此也没有 `--config`。

## 五、判定规则（确定性）

### 证据可达性

验收项的 `actual_path` 从 `ExecutionResult.evidence_view()` 读取，它暴露：

```
status / target
preserved_relations / lost_relations      ← 一等证据
artifact_count / artifacts
warnings / errors
+ outputs 的全部键
```

这样"关系是否被证明"就能直接判定，不必把证据塞进 `outputs`。

### 8 个算子

```
manual            Agent 提交结果（不能覆盖确定性算子）
tool_succeeded    引用的调用是否都成功
exists / truthy
equals / set_equals / count_equals
within_tolerance  支持向量逐分量比较
```

### Stage 聚合（顺序即优先级）

```
任一 required needs_human   → needs_approval
任一 required fail          → failed
任一 required unknown       → blocked
required 仅 warn            → degraded
任一非 required 项非 pass    → degraded（记录为 non-blocking）
required 全 pass            → succeeded
```

任一 required 非 pass 都会写入 `errors`；`resume_pointer` 指回该 Stage。非 required 的问题只降级、不阻塞，写入 `warnings`。

### Task 聚合

```
门未通过                       → blocked（suspended）
任一 Stage needs_approval     → needs_approval
任一 Stage failed             → failed
任一 Stage blocked            → blocked
required Stage 未全部关闭      → blocked（running）
有 Stage degraded             → degraded（completed）
否则                          → succeeded（completed）
```

## 六、调用路径

```
Agent 写计划
    ToolCall(call_id, target{owner,name}, arguments, depends_on)
        │
                │      Agent 自己的 MCP client
        │          → Blender / UE5 / ComfyUI MCP Server
        │          → 结果交回 record，成为该 Stage 的证据
        │
                       契约里是一等形状，但本仓库不附带任何可执行的 Toolset
```

**没有执行绑定，没有 provider 列表，没有注册步骤，没有发现索引。** 计划只做结构
校验：`validate_workflow_structure` 检查 `call_id` 唯一、`target` 有 owner 与 name、
`depends_on` 只指向更早声明的调用、每个调用至少支撑一个清单项。它不解析 `target`，
也不判断目标是否可用。

`record` 与 `open` 的三道校验替代了原先的绑定检查，而它们对 MCP 调用与项目 Tool
调用一视同仁：`call_id` 必须已在计划中声明，`target` 必须
与声明一致。

### MCP 调用是计划的一等成员

`ExecutionResult` 与 `ToolCall` 共用同一个 `target` 字段，因此宿主调用可以
完整进入调用图。原先"契约层表达不了 MCP 调用"的缺口已经消失：

```
① Agent 声明它真实要做的宿主调用
   {"call_id":"m1","target":{"owner":"ue5","name":"set_actor_transform"}}
   → open 接受（只做结构校验）

② Agent 执行该调用并把结果交回
   {"call_id":"m1","target":{"owner":"ue5","name":"set_actor_transform"},
    "status":"succeeded", ...}
   → record 接受，写入证据

③ 验收项可以直接引用它
   {"operator":"tool_succeeded","call_ids":["m1"]}
   → 依赖顺序、调用图完整性与自动判据全部覆盖到宿主工作
```

**宿主调用是计划的正式成员。** 依赖顺序、调用图完整性与自动判据都覆盖它。
`manual` 用于真正需要人工判断的验收项。

## 七、边界（有意为之）

| 边界 | 为什么 |
|---|---|
| 本仓库不含宿主可执行文件路径/子进程/插件 | 宿主的事归宿主的 MCP Server |
| 不执行任何调用，不含执行绑定或 provider 列表 | 执行是 Agent 的 MCP client 的事 |
| 不做 Tool 注册、发现、搜索 | 调用目标由 Agent 在计划里显式声明 |
| 不生成计划、不排序、不选下一个调用 | 那是 Agent 的判断 |
| 评估器不调用 Tool | 判定必须可复现 |
| 两套验收系统不合并 | 本仓库判"这个 Stage 达成本地目标"；`AI-Native-Evals` 判"任务是否真的完成"。前者是过程信号，后者是唯一外部有效结论 |

### 核心承诺

**调用返回 `succeeded` 不等于 Stage 完成。** Stage 只在冻结的验收项通过时完成。实测：空 `preserved_relations` 对 `truthy` 检查 → check `fail` → stage `failed` → exit 1。

## 八、目录

```
game-engine/
├── AGENTS.md                仓库级 Agent 规则
├── SKILL.md                 Skill 入口
├── guidance/                生命周期指引（7 份）
├── references/              宿主接入说明（3 份）
├── templates/               Workflow 模板 + 字段说明 + 指引模板
├── src/ainative/
│   ├── session_api/         Skill 加载 + Workflow 开启 + 验收会话
│   ├── cli/                 验收循环 CLI / state
│   ├── model/               纯数据结构（含 ToolCall / CallTarget）
│   ├── reading/             读 JSON、校验 Workflow 结构
│   └── acceptance/          确定性判定 + 汇总 + 确认门
├── tests/                   单元与集成测试
├── docs/                    架构、依赖、维护、验证、CLI
└── artifacts/               证据与归档
```
