# 验收循环 CLI

本仓库只暴露一个进程级 CLI：`python -m ainative.session`。Agent 自己写 plan、
自己执行每一次调用（宿主能力经它自己的 MCP Client 到达），再把自己的结果交给
Python，由 Python 按 Stage 冻结的 checklist 给出确定性判定。

**本仓库不执行任何调用。** 它没有项目 Toolset、没有执行绑定、也没有 provider
列表：plan 只做结构校验，调用由 Agent 自己完成。

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
| `open` | 校验 Agent 写的 plan，建立会话并写出初始 state | `--task`、`--workflow` |
| `record` | 提交一次已执行调用的结果作为证据 | `--result` |
| `item` | 提交一条 execution checklist 项的结果 | `--result` |
| `check` | 提交一条人工 acceptance check 的结果 | `--result` |
| `stage` | 按冻结的 checklist 评估并关闭一个 Stage | `--stage` |
| `finish` | 汇总最终的 TaskResult | — |
| `status` | 只读当前会话状态，不做任何修改 | — |

`--state` 是必需参数，指向会话状态文件（由 `open` 创建）。它是 Agent 已提交证据
的唯一载体：task、plan，以及一份**按提交顺序**记录的证据事件日志（调用结果、
checklist 结果、已关闭的 Stage）。顺序有意义：某个调用只有在它依赖的 Stage 关闭
之后才允许记录，因此重放必须按原顺序，不能当成无序集合。每次命令都是独立进程，
会话靠重放这份日志重建，判定因此是确定性的，文件里也不会出现 Agent 没有做过的
决定。

除 `open` 的 `--task` / `--workflow` 外，各命令只需要 `--state` 加上自己的那个参数。
没有 `--config`：plan 的校验是纯结构的，不依赖任何本机 provider 配置。

## 调用的形状

plan 里的每个调用都带 `call_id`、`kind` 和 `target`：

```json
{
  "call_id": "m1",
  "kind": "mcp",
  "target": {"owner": "ue5", "name": "set_actor_transform"},
  "arguments": {},
  "depends_on": []
}
```

- `kind` 是 `project_tool` 或 `mcp`。
- `target.owner` / `target.name`：对 `mcp` 是 MCP server 名与 tool 名；对
  `project_tool` 是 Toolset id 与 Tool id。两种调用在契约里同等一等，都在计划的
  调用图里参与 `depends_on` 与 `tool_succeeded` 判定。

**没有绑定，也没有 provider 检查。** 本仓库不解析 `target`，也不执行它——执行由
Agent 自己的 MCP Client 完成。因此 `kind: "mcp"` 的宿主调用是计划的正式成员，
不需要绕道 `manual`。

## 退出码

每条命令都打印一个 JSON 对象，退出码含义：

```text
0   结果非阻塞（succeeded / degraded）
1   结果阻塞或失败（failed / blocked / needs_approval）
2   命令本身没能跑起来（state 不可读、plan/结果 JSON 非法、字段缺失等）
```

`item` / `check` 提交的结果状态为 `fail` 或 `needs_human` 时同样退出 1。

退出码 2 时同样打印 JSON，形如
`{"status": "blocked", "command": "...", "errors": ["..."]}`；plan 反序列化失败会
指明出错的 JSON 路径，便于 Agent 直接修文档。

## 关键保证

一次调用返回 `succeeded` **不等于** Stage 完成。Stage 只在其冻结的 acceptance
check 通过时才完成。例如对 `preserved_relations` 做 `truthy` 检查而实际为空列表，
会得到 check `fail` → stage `failed` → 退出码 1。

acceptance check 通过 `ExecutionResult.evidence_view()` 读取证据，因此 `actual_path`
除了 `outputs` 里的键，还可以直接寻址一等证据：`status`、`kind`、`target`、
`preserved_relations`、`lost_relations`、`artifact_count`、`artifacts`、`warnings`、
`errors`。

## 单一入口

```text
ainative.session  接收 Agent 的 plan 与结果，返回 Stage 判定
```

它不生成计划、不调度 Stage、不执行调用、不替 Agent 决定下一步。
