# 验收循环 CLI

本仓库只暴露一个进程级 CLI：`python -m ainative.session`。Agent 自己写 Workflow、
自己执行每一次调用（宿主能力经它自己的 MCP Client 到达），再把自己的结果交给
Python，由 Python 按 Stage 冻结的 checklist 给出确定性判定。

**本仓库不执行任何调用。** 它没有项目 Toolset、没有执行绑定、也没有 provider
列表：Workflow 只做结构校验，调用由 Agent 自己完成。

## 运行

```powershell
# 方式一：源码在 PYTHONPATH 上
$env:PYTHONPATH='D:\work\AI-Native\game-engine\src'
python -m ainative.session --help

# 方式二：安装后使用 console script
pip install -e .
ainative-session --help
```

## 七个命令

```powershell
python -m ainative.session --state s.json --task task.json --workflow workflow.json open
python -m ainative.session --state s.json --result executed-call.json record
python -m ainative.session --state s.json --stage stage.validate_asset stage
python -m ainative.session --state s.json finish
python -m ainative.session --state s.json status
```

| 命令 | 作用 | 必需参数 |
|---|---|---|
| `open` | 校验 Agent 写的 Workflow，建立会话并写出初始 state | `--task`、`--workflow` |
| `record` | 提交一次已执行调用的结果作为证据 | `--result` |
| `item` | 提交一条 execution checklist 项的结果 | `--result` |
| `check` | 提交一条人工 acceptance check 的结果 | `--result` |
| `stage` | 按冻结的 checklist 评估并关闭一个 Stage | `--stage` |
| `finish` | 汇总最终的 TaskResult | — |
| `status` | 只读当前会话状态，不做任何修改 | — |
| `supersede` | 替换 Workflow 修订，归档旧修订及其证据 | `--workflow`（建议 `--reason`） |

`--state` 是必需参数，指向会话状态文件（由 `open` 创建）。它是 Agent 已提交证据
的唯一载体：task、当前 Workflow 修订、一份**按提交顺序**记录的证据事件日志（调用结果、
checklist 结果、已关闭的 Stage），以及被替换掉的修订。顺序有意义：某个调用只有在它依赖
的 Stage 关闭之后才允许记录，因此重放必须按原顺序，不能当成无序集合。每次命令都是独立
进程，会话靠重放这份日志重建，判定因此是确定性的，文件里也不会出现 Agent 没有做过的
决定。

除 `open` 的 `--task` / `--workflow` 外，各命令只需要 `--state` 加上自己的那个参数。

## 提交调用结果必须报出 target

`record` 的 `--result` **必须**带 `target`：

```json
{
  "call_id": "a1",
  "status": "succeeded",
  "target": {"owner": "ue5", "name": "set_actor_transform"}
}
```

它必须与 Workflow 里声明的逐字一致。省略会被拒绝：

```text
Execution result must report the target it ran: a1 declared ue5/set_actor_transform, got nothing
```

**为什么必填**：执行规则写着"用你选定的那个调用，不要悄悄换 target"。只在报出 target 时
才校验，这条规则就只是建议——不填就绕过了。校验要么成立，要么不成立。

## 每个命令能看到什么

`status` 会把**当前绑定的 Workflow** 一起报出来，Agent 不必回头读自己写的那个文件
（它可能已被改过，也可能随进程丢了）：

```json
{
  "workflow": {
    "workflow_id": "t:workflow", "revision": 2, "guidance": "host-operation",
    "replaced": ["t:workflow:r1"],
    "stages": [
      {
        "stage_id": "stage.a", "step_id": "move", "stage_kind": "change",
        "required": true, "closed": true, "side_effects_recorded": true,
        "calls": [{"call_id": "a1", "target": {"owner": "ue5", "name": "do_a"}}],
        "execution_checklist": [{"item_id": "i-a", "required": true}],
        "acceptance_checklist": [{"check_id": "k-a", "operator": "tool_succeeded", "required": true}]
      }
    ]
  }
}
```

`finish` 在 `blocked` 时指名还差哪些 Stage：

```json
{
  "verdict": "blocked",
  "errors": ["required Stages not closed: stage.a, stage.b"],
  "detail": {"details": {"outstanding_stages": ["stage.a", "stage.b"]}}
}
```

`item` / `check` 即使被拒绝也报出是哪一条：

```json
{
  "command": "item", "verdict": "blocked", "exit_code": 2,
  "detail": {"item_id": "not-declared", "status": "pass"},
  "errors": ["execution item is not declared in the Workflow: not-declared"]
}
```

## 替换 Workflow：`supersede`

Workflow 修订不可变（Workflow 规则第 8 条）。要改就产生新修订：

```powershell
python -m ainative.session --state s.json --workflow new.json --reason "需求变了" supersede
```

新修订必须用 `supersedes_workflow_id` 指名它替换的那一版；已经记录过进度的 state 不接受
无名替换，否则旧证据会被无声丢弃。

### 哪些 Stage 会被保留

**只有定义完全没变的 Stage 才继承。** 判据是**内容指纹**，不是 `stage_id`：

```
指纹 = hash(stage_kind + purpose + operation + required + calls + 两份清单)
```

因此：

| 情况 | 结果 |
|---|---|
| `stage_id` 相同、内容逐字相同 | **继承**：判定与证据一起带过去，不必重做 |
| `stage_id` 相同、但目标/清单/调用改了 | **作废**：旧判定对新定义无效，必须重做 |
| 只改了 `stage_id`（改名），别的不变 | **继承**：指纹不含 `stage_id` |
| 新出现的 Stage | 新做 |
| 消失的 Stage | 归档 |

同一名字不是同一件事：清单改了就是判据改了，旧 `pass` 不能算数。

### 已经做过的副作用

Python 看不到宿主，也无法撤销任何东西。它知道的是：**某个 Stage 的调用被记录过，就说明
那次调用真的对着一台活着的宿主跑过**。这类 Stage 会被追踪，并在替换时报告：

```json
{
  "carried_over":         ["stage.a"],
  "invalidated":          ["stage.b"],
  "side_effects_at_risk": ["stage.b"]
}
```

`side_effects_at_risk` 是**已经动过世界、又因为定义变了而被作废**的 Stage。重跑它意味着
同一个改动可能施加两次。

**这类调用会被拒绝**，除非 Agent 显式确认：

```powershell
# 被拒：call b1 曾在 r1 上跑过
python -m ainative.session --state s.json --result b1.json record
#   -> call b1 has already run against a live host (revision w:r1) ...

# 显式确认后才放行
python -m ainative.session --state s.json --result b1.json --confirm-side-effects record
```

**为什么拦这里而不是拦 `stage`**：`stage` 只是按已提交的证据判定，重复调用它是幂等的；
真正会重复施加改动的是**再跑一次调用**。所以闸门放在 `record`。

`stage` 的输出里也有 `side_effects_recorded`（该 Stage 是否已有调用跑过宿主）。

### 归档

被替换的修订连同它的证据、作废原因、以及当时已产生副作用的 Stage 一起存进
`state.revisions[]`。审计链完整：**当时想做什么、做到了哪一步、因为什么被放弃**。
归档的事件**不会**在新修订上重放——它们的 `call_id` 属于旧定义。
没有 `--config`：Workflow 的校验是纯结构的，不依赖任何本机 provider 配置。

## 调用的形状

Workflow 里的每个调用都带 `call_id` 和 `target`：

```json
{
  "call_id": "m1",
  "target": {"owner": "ue5", "name": "set_actor_transform"},
  "arguments": {},
  "depends_on": []
}
```

- `target.owner` / `target.name`：MCP server 名与它上面的 tool 名，在 Workflow
  的调用图里参与 `depends_on` 与 `tool_succeeded` 判定。

**没有绑定，也没有 provider 检查。** 本仓库不解析 `target`，也不执行它——执行由
Agent 自己的 MCP client 完成。因此宿主调用是 Workflow 的正式成员，
不需要绕道 `manual`。

## 输出信封

每条命令都打印**同一个信封**：相同的键、相同的顺序。调用方不需要知道跑的是哪条
命令、载荷嵌得多深，就能读出结论。

```json
{
  "command": "stage",
  "ok": false,
  "verdict": "blocked",
  "exit_code": 1,
  "detail": { "...该命令自己的载荷..." },
  "errors": ["required Stage checks lack evidence: ran"]
}
```

| 键 | 含义 |
| --- | --- |
| `command` | 哪条命令产生的 |
| `ok` | 是否非阻塞（等价于 `exit_code == 0`） |
| `verdict` | 发生了什么，**统一词汇** |
| `exit_code` | 进程退出码，冗余写进 JSON，调用方不必读退出码 |
| `detail` | 该命令自己的载荷；永远是对象 |
| `errors` | 永远是数组；成功时为空 |

## 统一词汇

`verdict` 对所有命令用同一套词。Stage 与 Task 的结果本来就说 `TaskStatus`；清单项的
`CheckStatus` **映射**过去，所以调用方只需匹配一套词：

| 清单项 | → `verdict` |
| --- | --- |
| `pass` | `succeeded` |
| `warn` | `degraded` |
| `fail` | `failed` |
| `unknown` | `blocked` |
| `needs_human` | `needs_approval` |

因此 `record` 的 `succeeded` 与 `item` 的 `pass` 都报 `"verdict": "succeeded"`，
调用方一处判断即可。

## 退出码

```text
0   结果非阻塞（succeeded / degraded）
1   结果阻塞或失败（failed / blocked / needs_approval）
2   命令本身没能跑起来（state 不可读、Workflow/结果 JSON 非法、字段缺失等）
```

等价关系写在信封里：`"ok": true` ⟺ `"exit_code": 0`。

退出码 2 表示**命令自己失败，不是任务失败**——Workflow 与已记录的证据都没动，
调用方修好输入重试即可。这类输出同样是标准信封，`exit_code` 为 2；Workflow
反序列化失败会在 `errors` 里指明出错的 JSON 路径，便于 Agent 直接修文档。

## 关键保证

一次调用返回 `succeeded` **不等于** Stage 完成。Stage 只在其冻结的 acceptance
check 通过时才完成。例如对 `preserved_relations` 做 `truthy` 检查而实际为空列表，
会得到 check `fail` → stage `failed` → `verdict` 为 `failed`、退出码 1。

acceptance check 通过 `ExecutionResult.evidence_view()` 读取证据，因此 `actual_path`
除了 `outputs` 里的键，还可以直接寻址一等证据：`status`、`target`、
`preserved_relations`、`lost_relations`、`artifact_count`、`artifacts`、`warnings`、
`errors`。

## 单一入口

```text
ainative.session  接收 Agent 的 Workflow 与结果，返回 Stage 判定
```

它不生成 Workflow、不调度 Stage、不执行调用、不替 Agent 决定下一步。
