# 架构与数据流

> 本文件回答两个问题：**系统由哪几层构成**、**一次任务是怎样的数据流**。
> 结论都取自实际代码，不是设计意图。

## 一、一句话架构

**Agent 决定做什么并亲自执行；Python 只做两件它不能委托的事——校验计划结构，和按 Agent 自己冻结的清单给出确定性判定。**

```
┌─────────────────────────────────────────────────────────────┐
│  Agent（Codex 等）                                          │
│  读指引 · 组合节点 · 定计划 · 逐个调用 · 判断下一步          │
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
| Skill 文档 | 仓库根：`SKILL.md`、`guidance/`、`templates/` | 生命周期指引、形状契约 | 不是运行时 |
| 模型层 | `model/` | 数据结构（纯 dataclass） | 无行为 |
| 读取层 | `reading/` | 读 JSON；按 `templates/workflow.schema.json` 检查文档的形状与格式（`schema.py`），再检查 schema 表达不了的语义（`tree_validate.py`） | 不生成计划、不排序、不解析调用目标 |
| 验收层 | `acceptance/` | 按清单确定性判定、整棵树自底向上汇总、确认门 | 不调用任何 Tool |
| 会话层 | `session_api/` | 加载 Skill、记录证据、关闭节点、汇总 | 不选择、不执行调用 |
| 入口 | `cli/commands.py` | 唯一的进程级 CLI | — |

### 关键分层原则

**模型层是纯数据。** `model/` 下全是 `@dataclass(frozen=True, slots=True)`，没有方法做决定，只有 `to_dict()` 和少量派生属性（如 `WorkflowTree.stage_paths`、`WorkflowTree.nodes`、`WorkflowTree.fingerprints()`）。

**模型层不排序、不生成、只做派生。** `walk()` / `resolve()` / `leaves()` / `plan_reuse()` 都是纯函数：它们把 Agent 已经写好的树读出来，不决定先做哪个节点。规划是 Agent 的事。

**验收层不认识 Tool。** `StageAcceptanceEvaluator.evaluate()` 只接收：一个 STAGE 叶节点（`WorkflowNode`）、它的路径、若干 `ExecutionResult`、以及 Agent 提交的清单结果。它不解析、不绑定、不执行。树的递归由 `acceptance/tree_evaluator.py` 拥有：它把每个 STAGE 叶交给该求值器，再自底向上算出每个 WORKFLOW 节点的判定——叶子的语义只定义一次。

## 三、数据结构

### 输入侧（Agent 写）

```
TaskContract                        这次任务"是什么"
├── task_id / objective
├── route                           host_operation | asset_transfer | artifact_pipeline
├── asset_type / direction
├── preserve_relations              必须存活的关系
├── guidance                        Agent 想读哪份指引（可选，自由字符串）
├── source_context / target_context  从哪里到哪里
├── confirmation_required            是否需要先确认意图
└── metadata

WorkflowTree                        一个任务 = 一棵工作流修订
├── workflow_id / guidance / route
├── root                            WorkflowNode：整棵树的根，路径为 "/"
├── revision / status
├── supersedes_workflow_id / replacement_reason
└── recovery_pointer / warnings

WorkflowNode                        一个节点：叶，或复合
├── node_id                         只在**同级兄弟**之间唯一
├── kind                            stage | workflow
├── purpose / required
├── depends_on[]                    从本节点出发写的节点引用（'../mass' 是兄弟）
├── guidance / recovery / metadata
├── kind == stage   → stage        StageBody
└── kind == workflow
    ├── children[]                  WorkflowNode
    └── acceptance_checklist[]      NodeCheck：读一个**后代**

StageBody                           一个 STAGE 叶声明的工作
├── stage_kind                      change | investigation | planning
├── calls[]                         ToolCall
├── execution_checklist[]           ExecutionChecklistItem：做什么，防漏
└── acceptance_checklist[]          NodeCheck：证明什么，防"没报错就算过"

NodeCheck                           一条验收项
├── check_id / description / required
├── source_call_id                  STAGE 叶：读自己声明的一条调用
├── source_node                     WORKFLOW 复合：读一个后代，相对路径
├── operator / actual_path / expected / tolerance
└── metadata

ToolCall                             一次 Agent 声明的调用
├── call_id                          只在自己的 STAGE 内唯一
├── target                          CallTarget：owner + name
├── arguments
└── depends_on                       同一 STAGE 内的 call_id
```

**阶段（phase）不是独立类型。** 它就是一个用来分组的 WORKFLOW 节点。原先的三层
`Workflow -> WorkflowStep -> StageRequest` 与全局唯一的 `stage_id` 都不存在了；模型里
只有一种节点，靠 `kind` 分叶与复合。

**身份是路径，不是 `node_id`。** 一条路径由各级 `node_id` 用 `/` 连接，每段都以 `/`
结尾：`/step-1/validate-asset/`，根节点的路径是 `/`。`node_id` 只在同级兄弟之间唯一
——这正是"两棵子树各自声明一个 `mass`"能成立的原因——所以跨层引用一律用路径。
`WorkflowTree.node_at()` 只按路径解析；它也接受裸 `node_id`，但仅当全树只有一个节点
用这个名字时，歧义的名字按"找不到"处理，而不是随便挑一个。

**指纹是递归的。** `node_fingerprint()` 的摘要把整棵子树算进去（`kind` + `purpose`
+ `required` + `depends_on` + `recovery`，加上叶子的整个 stage body，或复合节点的
验收项与逐个子节点指纹），因为复合节点的
完成取决于子节点产出了什么：深处一个叶子的改动必须让每个依赖它的祖先失效。
摘要**不含 `node_id`**，所以改名或移动子树不会把它变成另一件事，整支未改动的分支
可以在修订之间原样继承。替换修订时用它判断某个节点是否还是同一件事，见
[docs/cli.md](cli.md) 的 `supersede` 一节。

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

NodeResult                          树的判定（自底向上，子节点判定嵌在里面）
├── path / node_id / kind / status    status 用**节点**词表
├── required / skipped
├── item_results[] / check_results[]
├── children[]                        子节点判定，逐层嵌套
└── blocked_by[] / reason

StageResult                         关闭一个节点时的判定
├── node_path                        节点的唯一身份（原 stage_id + step_id）
├── status                           用**任务**词表
├── call_ids[] / execution_results[]
├── execution_item_results[]
├── check_results[]
├── execution_summary / acceptance_summary
├── outputs / artifacts / warnings / errors
└── resume_pointer

TaskResult                          最终汇总
├── status / route / workflow_id
├── workflow_revision / workflow_revision_id / workflow_status
├── nodes_completed[] / node_results[]
├── preserved_relations / lost_relations
├── artifacts / details / warnings / errors
└── next_action / resume_pointer
```

## 四、数据流：一次完整任务

```
① Agent 读文档
   AGENTS.md → SKILL.md → 完整性门 → templates/ → guidance/
   （需要宿主时读 docs/DEPENDENCIES.md）

② Agent 写 TaskContract（JSON）

③ Agent 写计划（JSON）
   为每个 required STAGE 叶冻结两份清单
   需要"父节点对子节点产出下判断"时，再给 WORKFLOW 节点写读后代的验收项

④ python -m ainative.session open --task --workflow
   ├── 读 JSON → 框架契约（workflow_from_dict）
   ├── 校验结构（validate_tree_structure）
   │   ├── 同级 node_id 必须唯一；depends_on 从本节点出发解析，可跨分支，不得绝对路径
   │   ├── 依赖图必须无环（含隐式的「复合等待自己的子节点」这条边）
   │   ├── WORKFLOW 节点必须有至少一个子节点
   │   ├── STAGE：必须有 stage body；required 时必须至少一条 call 与两份清单
   │   ├── STAGE：验收项只能读自己声明的 call（source_call_id），不得用 source_node
   │   ├── WORKFLOW：不得携带 stage body；验收项必须用 source_node 指向一个后代
   │   └── 每个 call 至少支撑一个清单项
   └── 写 state.json

⑤ Agent 执行（自己的 MCP client）
   一次一个调用，不静默替换目标

⑥ python -m ainative.session record --result <已执行调用的 JSON>
   ├── 校验 call_id 已在计划中声明
   ├── 校验 target 与计划一致
   └── 追加到有序事件日志，重放全部事件

⑦ python -m ainative.session stage --stage /step-1/validate-asset/
   └── 按路径取节点：STAGE 交给 StageAcceptanceEvaluator，
       WORKFLOW 先判定整棵子树再算自己的验收项

⑧ 按该节点的 StageResult 决定：继续 / 重试 / 等人工 / 补证据 / 换方案

⑨ python -m ainative.session finish
   └── 汇总 TaskResult
```

`--stage` 收的是**路径**：`node_id` 只在同级之间唯一，裸 id 无法唯一指名一个节点。
路径可以指向 STAGE 叶，也可以指向 WORKFLOW 复合——关闭一个复合节点会判定它的整棵
子树并给出汇总。`item` 与 `check` 也接受 `--stage`，用于在某个 item/check id 被多个
节点声明时点名归属；歧义的 id 会被拒绝，而不是替 Agent 猜一个。

### 为什么状态是"有序事件日志"

每次 CLI 调用是独立进程，所以要落盘。但**顺序不能丢**：一个调用只有在其依赖的节点
关闭之后才允许记录。若用扁平列表回放，会重现已满足的依赖失败。

**每个事件都按路径写明它属于哪个节点。** `node_id` 只在同级唯一，一个只带裸 id 的
事件在两棵子树声明同名节点后就无法归属；路径是存下来的，不是回放时重新推出来的。

```json
{
  "version": 1,
  "task":  { ... },
  "workflow": { ... },
  "revisions": [],
  "events": [
    {"type": "execution_result", "payload": { "call_id": "a1", "...": "..." }},
    {"type": "node_closed",      "payload": {"node_path": "/step-1/validate-asset/"}},
    {"type": "check",            "payload": {"check_id": "k-a", "status": "pass",
                                             "node_path": "/step-1/validate-asset/"}},
    {"type": "node_closed",      "payload": {"node_path": "/step-1/"}}
  ]
}
```

事件类型只有四种：

```
execution_result   一次已执行调用的结果（按 call_id 归属到声明它的 STAGE）
execution_item     一条执行清单项结果（payload 额外带 node_path）
check              一条人工验收项结果（payload 额外带 node_path）
node_closed        一个节点已关闭（payload：{"node_path": ...}）
```

被替换掉的修订连同它的事件存进 `revisions[]`。task 与 workflow 都存在状态里，所以
`open` 之后各命令不必重复传 `--task` / `--workflow`。计划只做结构校验，不依赖任何
本机 provider 配置，因此也没有 `--config`。

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

这样"关系是否被证明"就能直接判定，不必把证据塞进 `outputs`。复合节点的验收项读的
不是证据，而是**某一条后代判定的结论词**（见下）。

### 两套词表（不要混）

| | 用在哪 | 取值 |
|---|---|---|
| **节点判定** `CheckStatus` | `NodeResult.status`、清单项、check | `pass` / `warn` / `fail` / `unknown` / `needs_human` |
| **任务状态** `TaskStatus` | `StageResult.status`、`TaskResult.status`、CLI 信封的 `verdict` | `succeeded` / `degraded` / `blocked` / `failed` / `needs_approval` |

节点判定按固定映射投影到任务状态，CLI 的 `verdict` 因此对所有命令只有一套词。

### 8 个算子

```
manual            Agent 提交结果（不能覆盖确定性算子）
tool_succeeded    引用的调用是否都成功
exists / truthy
equals / set_equals / count_equals
within_tolerance  支持向量逐分量比较
```

### 树的自底向上判定

`acceptance/tree_evaluator.py` 按顺序回答"一个节点什么时候算完成"：

```
① STAGE 叶      每个 required 执行项被满足，且每个 required 验收项通过
                （由 StageAcceptanceEvaluator 判定，叶的语义只定义一次）
② WORKFLOW 复合 每个 required 子节点完成，**并且**它自己的验收项通过
③ 可选节点被省略 → skipped（status 为 unknown：没跑过的活儿没有证据，
                 报 pass 就是撒谎），不拖垮父节点
④ required 的 unknown / needs_human 让**每个祖先**也是 unknown：
                 证据不全的判定不是判定，这正是"只看调用返回没有"的父节点会掩盖的失败
```

复合节点的验收项读的是后代判定：`source_node` 指明一个后代（相对本节点的路径，
不能指向自己），观察到的值就是那个后代的结论词。因此 schema 把这类 `expected`
限定在**节点词表**里，它不是后代列表，也不是 `succeeded` 这类任务状态——写成后者
的检查永远不会通过。

### STAGE 叶 → 报告状态（顺序即优先级）

下表已经是**任务词表**：叶的节点判定由 `CHECK_STATUS_TO_TASK_STATUS` 固定投影过去。

```
任一 required needs_human   → needs_approval
任一 required fail          → failed
任一 required unknown       → blocked
required 仅 warn            → degraded
任一非 required 项非 pass    → degraded（记录为 non-blocking）
required 全 pass            → succeeded
```

任一 required 非 pass 都会写入 `errors`；`resume_pointer` 指回该节点。非 required 的
问题只降级、不阻塞，写入 `warnings`。

### WORKFLOW 复合的聚合

```
任一 required 子节点 fail          → fail
任一 required 子节点 unknown/needs_human，或自己的检查无法判定 → unknown
自己的检查 fail                    → fail
自己的检查 warn                    → warn
否则                               → pass
```

失败的子节点与无法判定的子节点都会被记进 `blocked_by`，两者的区别保留着：
"断了"和"看不出来"不是一回事。复合节点被关闭时，这个节点判定同样按固定映射投影成
`StageResult.status`。

### Task 聚合

```
门未通过                        → blocked（suspended）
任一节点 needs_approval         → needs_approval
任一节点 failed                 → failed
任一节点 blocked                → blocked
required 节点未全部关闭          → blocked（running）
有节点 degraded                 → degraded（completed）
否则                            → succeeded（completed）
```

关闭一个复合节点会连带关闭它子树里已经满足的部分；`outstanding_nodes` 只列 required
且尚未关闭的路径，`finish` 在 blocked 时把它们写进 `errors` 和
`details.outstanding_nodes`。

## 六、调用路径

```
Agent 写计划
    ToolCall(call_id, target{owner,name}, arguments, depends_on)
        │
                │      Agent 自己的 MCP client
        │          → Blender / UE5 / ComfyUI MCP Server
        │          → 结果交回 record，成为该 STAGE 的证据
        │
                       契约里是一等形状，但本仓库不附带任何可执行的 Toolset
```

**没有执行绑定，没有 provider 列表，没有注册步骤，没有发现索引。** 计划只做结构
校验：`validate_tree_structure` 检查同级 `node_id` 唯一、`depends_on` 从声明节点出发
可解析到某个节点（可跨分支，不能绝对路径、不能是裸 id）、依赖图无环、STAGE 与 WORKFLOW
各自允许携带什么、每个调用至少支撑一个清单项。它不解析 `target`，也不判断目标是否可用。

`record` 与 `open` 的校验替代了原先的绑定检查，而它们对 MCP 调用与项目 Tool
调用一视同仁：`call_id` 必须已在计划中声明，`target` 必须与声明一致。

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
| 两套验收系统不合并 | 本仓库判"这个节点达成本地目标"；`AI-Native-Evals` 判"任务是否真的完成"。前者是过程信号，后者是唯一外部有效结论 |

### 核心承诺

**调用返回 `succeeded` 不等于节点完成。** STAGE 只在冻结的验收项通过时完成。实测：空
`preserved_relations` 对 `truthy` 检查 → check `fail` → stage `failed` → exit 1。

## 八、目录

```
game-engine/
├── AGENTS.md                仓库级 Agent 规则
├── SKILL.md                 Skill 入口
├── guidance/                生命周期指引（单文档或目录两种形态）
├── templates/               Workflow schema + 结果契约 + 指引模板
├── src/ainative/
│   ├── session_api/         Skill 加载 + Workflow 开启 + 验收会话
│   ├── cli/                 验收循环 CLI / state
│   ├── model/               纯数据结构（含 ToolCall / CallTarget / WorkflowTree）
│   ├── reading/             读 JSON、校验 Workflow 结构
│   └── acceptance/          确定性判定 + 整树汇总 + 确认门
├── tests/                   单元与集成测试
├── docs/                    架构、依赖、维护、验证、CLI
└── artifacts/               证据与归档
```
