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

`--state` 是必需参数，指向会话状态文件（由 `open` 创建）。它是 Agent 已提交证据
的唯一载体：task、Workflow，以及一份**按提交顺序**记录的证据事件日志（调用结果、
checklist 结果、已关闭的 Stage）。顺序有意义：某个调用只有在它依赖的 Stage 关闭
之后才允许记录，因此重放必须按原顺序，不能当成无序集合。每次命令都是独立进程，
会话靠重放这份日志重建，判定因此是确定性的，文件里也不会出现 Agent 没有做过的
决定。

除 `open` 的 `--task` / `--workflow` 外，各命令只需要 `--state` 加上自己的那个参数。
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
