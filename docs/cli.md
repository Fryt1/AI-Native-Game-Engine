# 验收循环 CLI

本仓库只暴露一个进程级 CLI：`python -m ainative.session`。Agent 自己写 Workflow、
自己执行每一次调用（宿主能力经它自己的 MCP Client 到达），再把自己的结果交给
Python，由 Python 按节点冻结的 checklist 给出确定性判定。

**本仓库不执行任何调用。** 它没有项目 Toolset、没有执行绑定、也没有 provider
列表：Workflow 只做结构校验，调用由 Agent 自己完成。

## 运行

```powershell
# 方式一：源码在 PYTHONPATH 上（路径按你自己放仓库的位置写）
$env:PYTHONPATH='<repository root>/src'
python -m ainative.session --help

# 方式二：安装后使用 console script
pip install -e .
ainative-session --help
```

## 命令

```powershell
python -m ainative.session --state s.json --task task.json --workflow workflow.json open
python -m ainative.session --state s.json --result executed-call.json record
python -m ainative.session --state s.json --stage /step-1/validate-asset/ stage
python -m ainative.session --state s.json finish
python -m ainative.session --state s.json status
```

| 命令 | 作用 | 必需参数 |
|---|---|---|
| `open` | 校验 Agent 写的 Workflow，建立会话并写出初始 state | `--task`、`--workflow` |
| `record` | 提交一次已执行调用的结果作为证据 | `--result`（调用 id 有歧义时加 `--stage`） |
| `item` | 提交一条 execution checklist 项的结果 | `--result` |
| `check` | 提交一条人工 acceptance check 的结果 | `--result` |
| `stage` | 按冻结的 checklist 评估并关闭一个节点（叶或复合） | `--stage` |
| `finish` | 汇总最终的 TaskResult | — |
| `status` | 只读当前会话状态，不做任何修改 | — |
| `supersede` | 替换 Workflow 修订，归档旧修订及其证据 | `--workflow`（建议 `--reason`） |

`--state` 是必需参数，指向会话状态文件（由 `open` 创建）。它是 Agent 已提交证据
的唯一载体：task、当前 Workflow 修订、一份**按提交顺序**记录的证据事件日志（调用结果、
checklist 结果、已关闭的节点），以及被替换掉的修订。顺序有意义：某个调用只有在它依赖
的节点关闭之后才允许记录，因此重放必须按原顺序，不能当成无序集合。每次命令都是独立
进程，会话靠重放这份日志重建，判定因此是确定性的，文件里也不会出现 Agent 没有做过的
决定。

`open` 与 `supersede` 在收下文档前跑**两层**校验，两层都会拒绝：

| 层 | 检查什么 | 失败时的说法 |
|---|---|---|
| `reading/schema.py` 对照 `templates/workflow.schema.json` | 形状与格式（必填字段、枚举、id 字符集、`expected` 的词表） | `workflow does not match the spec: #/root/...` |
| `reading/tree_validate.py` | schema 表达不了的语义（同级唯一、依赖成环、检查读的是哪一侧） | 规则号 + 位置，如 `C4`、`V3` |

spec 先跑。两层都会拒绝是故意的：只有形状的文档不是 Workflow，只有语义的文档也不合定义。
spec 文件读不到时**失败关闭**——缺 spec 不等于可以不校验。

除 `open` 的 `--task` / `--workflow` 外，各命令只需要 `--state` 加上自己的那个参数。

## 节点用路径指名

`--stage` 收的是**路径**，不是 id。`node_id` 只在同级兄弟之间唯一——这正是"两棵子树
各自声明一个 `mass`"能成立的原因——所以裸 id 无法唯一指名一个节点。

路径由各级 `node_id` 用 `/` 连接，每段都以 `/` 结尾，根节点是 `/`：

```text
/                         Workflow 的根节点
/step-1/                  一个 WORKFLOW 复合（phase / 容器）
/step-1/validate-asset/   一个 STAGE 叶
```

`--stage` 可以指向 STAGE 叶，也可以指向 WORKFLOW 复合：**关闭复合节点会判定它的整棵
子树**并给出汇总判定，因为复合节点的结论本来就挣自它的子节点。

`item` 与 `check` 也接受 `--stage`，用于在某个 item/check id 被多个节点声明时点名归属。
歧义的 id 会被拒绝，而不是替 Agent 猜一个：

```text
execution item is not declared by exactly one node in the Workflow: built;
name the node with --stage when the id is ambiguous
```

提交的 JSON 里也可以直接写 `node_path`，效果与 `--stage` 相同。

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

## 提交清单结果：`item` 与 `check`

这两个命令提交的是**清单项**的结果，形状和调用结果不同：

```json
{"item_id": "reviewed", "status": "pass", "evidence_refs": ["note:review-2024-01"]}
{"check_id": "signed",  "status": "pass", "evidence_refs": ["note:signoff-2024-01"]}
```

**`evidence_refs` 不是可选装饰。** 清单项和检查默认 `evidence_required: true`：报
`pass`/`warn` 却不带证据引用的结果会被降级成 `unknown`，于是那个节点永远关不上。

关键在于**报错发生在后面一步，不在提交这一步**：

```text
$ … --result check.json --stage /work/review/ check
{"verdict": "succeeded"}          ← 收下了

$ … --stage /work/review/ stage
{"verdict": "blocked", "errors": [
  "'signed' reports pass but names no evidence; a submitted result must carry
   'evidence_refs', a non-empty list of strings naming what was looked at"]}
```

它是一个**非空字符串数组**，内容由你定：文件路径、哈希、人类备注的编号都行。引擎不解析、
不校验它指向的东西存不存在——它记的只是"你凭什么这么说"。

`record` 不需要自己填：调用结果的引用由引擎按 `execution-result:<call_id>` 自动生成。
所以只有 `item` 和 `check` 会遇到这个要求。把 `evidence_required` 显式写成 `false`
也可以免除，但那等于声明"这一项不需要任何凭据"——想清楚再写。

## 每个命令能看到什么

`status` 会把**当前绑定的 Workflow** 一起报出来，Agent 不必回头读自己写的那个文件
（它可能已被改过，也可能随进程丢了）。列出的是**每一个节点**，不只是叶：复合节点
同样可以关闭，而它的判定正是父节点要读的那个：

```json
{
  "workflow": {
    "workflow_id": "t:workflow", "revision": 2,
    "replaced": ["t:workflow:r1"],
    "nodes": [
      {
        "node_path": "/step-1/", "node_id": "step-1", "kind": "workflow",
        "purpose": "校验资产", "required": true,
        "closed": false, "side_effects_recorded": false,
        "calls": [],
        "execution_checklist": [],
        "acceptance_checklist": [
          {"check_id": "asset-ok", "operator": "equals", "required": true}
        ]
      },
      {
        "node_path": "/step-1/validate-asset/", "node_id": "validate-asset",
        "kind": "stage", "purpose": "校验资产", "required": true,
        "closed": true, "side_effects_recorded": true,
        "calls": [{"call_id": "a1", "target": {"owner": "ue5", "name": "do_a"}}],
        "execution_checklist": [{"item_id": "i-a", "required": true}],
        "acceptance_checklist": [
          {"check_id": "k-a", "operator": "tool_succeeded", "required": true}
        ]
      }
    ]
  }
}
```

`finish` 在 `blocked` 时指名还差哪些节点（路径按字典序，`details.outstanding_nodes`
与顶层 `errors` 同时给出）：

```json
{
  "verdict": "blocked",
  "errors": ["required nodes not closed: /step-1/, /step-1/validate-asset/"],
  "detail": {"details": {"outstanding_nodes": ["/step-1/", "/step-1/validate-asset/"]}}
}
```

`item` / `check` 即使被拒绝也报出是哪一条：

```json
{
  "command": "item", "verdict": "blocked", "exit_code": 2,
  "detail": {"item_id": "not-declared", "status": "pass"},
  "errors": ["execution item is not declared by exactly one node in the Workflow: not-declared; name the node with --stage when the id is ambiguous"]
}
```

## 替换 Workflow：`supersede`

Workflow 修订不可变（Workflow 规则第 8 条）。要改就产生新修订：

```powershell
python -m ainative.session --state s.json --workflow new.json --reason "需求变了" supersede
```

新修订必须用 `supersedes_workflow_id` 指名它替换的那一版；已经记录过进度的 state 不接受
无名替换，否则旧证据会被无声丢弃。

### 哪些节点会被保留

**只有"路径相同、内容指纹也相同"的节点才继承。** 判据是**递归内容指纹**，不是
`node_id`：

```text
指纹 = hash( kind + purpose + required + depends_on + recovery
             + 叶子的 stage body（stage_kind + calls + 两份清单）
             + 复合节点的验收项 + 逐个子节点指纹 )
指纹不含 node_id
```

因为指纹把整棵子树算进去，改动的传播是沿祖先链的：深处一个叶子变了，只有它和它的
祖先作废，旁边的兄弟分支照旧继承。

| 情况 | 结果 |
|---|---|
| 路径相同、内容指纹相同 | **继承**：判定与证据一起带过去，不必重做 |
| 路径相同、但目标/清单/调用改了 | **作废**：旧判定对新定义无效，必须重做 |
| 只改了 `node_id`（改名） | **不继承**：指纹不含 `node_id`，但继承还要求**路径相同**；改名后原路径上的节点消失了，新路径上的节点是新出现的 |
| 新出现的节点 | 新做 |
| 消失的节点 | 归档 |

同一路径不是同一件事：清单改了就是判据改了，旧 `pass` 不能算数。

### 已经做过的副作用

Python 看不到宿主，也无法撤销任何东西。它知道的是：**某个节点的调用被记录过，就说明
那次调用真的对着一台活着的宿主跑过**。这类节点会被追踪，并在替换时报告：

```json
{
  "carried_over":         ["/step-1/", "/step-1/validate-asset/"],
  "invalidated":          ["/step-2/apply-change/"],
  "side_effects_at_risk": ["/step-2/apply-change/"]
}
```

`carried_over` 列出新修订里所有"路径与指纹都没变"的节点，复合节点也算；`invalidated`
与 `side_effects_at_risk` 只列 **STAGE 叶**——前者是新修订里没有继承的叶，后者是其中
**已经动过世界**的那些（只有叶声明调用，也只有叶会重跑）。重跑 `side_effects_at_risk`
里的节点，意味着同一个改动可能施加两次。

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

`stage` 的输出里也有 `side_effects_recorded`（该节点是否已有调用跑过宿主）。

### 归档

被替换的修订连同它的证据、作废原因、以及当时已产生副作用的节点一起存进
`state.revisions[]`。审计链完整：**当时想做什么、做到了哪一步、因为什么被放弃**。

事件按**新修订**的声明分派：属于继承节点的事件原样带到新修订继续有效（同一份工作、
同一份证据，旧判定仍然算数）；其余事件归档，**不会**在新修订上重放——它们的 `call_id`
属于旧定义。

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
- `call_id` 只在自己的 STAGE 内保证唯一；`depends_on` 引用的也是同一 STAGE 内的
  call id。

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

`stage` 的 `detail` 就是该节点的 `StageResult`，其中 `node_path` 是节点的唯一身份。

## 统一词汇

`verdict` 对所有命令用同一套词，而且用的是**任务**词表。节点判定（`CheckStatus`）
**映射**过去，所以调用方只需匹配一套词：

| 节点判定 / 清单项 | → `verdict`（任务词表） |
| --- | --- |
| `pass` | `succeeded` |
| `warn` | `degraded` |
| `fail` | `failed` |
| `unknown` | `blocked` |
| `needs_human` | `needs_approval` |

因此 `record` 的 `succeeded` 与 `item` 的 `pass` 都报 `"verdict": "succeeded"`，
调用方一处判断即可。反过来不要混：`TaskResult.status` 里不会出现 `pass`，节点判定
里也不会出现 `succeeded`。

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

一次调用返回 `succeeded` **不等于**节点完成。STAGE 只在其冻结的 acceptance
check 通过时才完成。例如对 `preserved_relations` 做 `truthy` 检查而实际为空列表，
会得到 check `fail` → stage `failed` → `verdict` 为 `failed`、退出码 1。

WORKFLOW 复合节点同理，而且更严：它要求每个 required 子节点完成**并且**自己的验收项
通过。一个 required 后代只要 `unknown`/`needs_human`，整条祖先链都是 `unknown`
（映射为 `blocked`），而不是 `failed`——证据不全和"断了"不是一回事。

acceptance check 通过 `ExecutionResult.evidence_view()` 读取证据，因此 `actual_path`
除了 `outputs` 里的键，还可以直接寻址一等证据：`status`、`target`、
`preserved_relations`、`lost_relations`、`artifact_count`、`artifacts`、`warnings`、
`errors`。复合节点的验收项读的不是证据，而是 `source_node` 指明的**那一个后代**的
结论词（`pass` / `warn` / `fail` / `unknown` / `needs_human`）。

## 单一入口

```text
ainative.session  接收 Agent 的 Workflow 与结果，返回节点判定
```

它不生成 Workflow、不调度节点、不执行调用、不替 Agent 决定下一步。
