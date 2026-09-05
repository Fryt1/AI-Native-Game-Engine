# Codex Session Timeline Analyzer（外部工具接入说明）

分析 Codex Agent 会话的输入/输出、工具调用耗时、token 用量和瓶颈。
**这是社区只读工具，不属于本项目运行时，不改仓库任何 Agent/Skill/代码逻辑。**

## 来源

- 仓库: https://github.com/faizlee/codex-session-timeline-analyzer（MIT，只读分析 rollout JSONL）
- 本地安装: `D:\work\AI-Native\tools\codex-session-timeline-analyzer`（git clone）
- 已用 `pip install -e` 安装为全局命令 `codex-session-timeline`（Python 3.11，无第三方依赖）

## 它读什么

Codex Desktop/CLI 每次会话都会在 `C:\Users\27648\.codex\sessions\<yyyy>\<mm>\<dd>\rollout-*.jsonl`
落盘完整记录，包含：

- `session_meta`：系统提示、模型、cwd、git 信息
- `turn_context`：每轮上下文（Agent 实际看到的输入）
- `response_item.function_call`：Agent 的工具调用（名称 + JSON 参数）
- `response_item.function_call_output`：工具返回（通过 `call_id` 与调用配对）
- `token_count` / `token_usage_record`：每轮/每次 token 用量
- `event_msg` / `item_completed` / `world_state` 等时间事件

## 常用命令

```powershell
# 0) 便捷脚本：分析最新会话并生成 HTML（推荐）
powershell -ExecutionPolicy Bypass -File .\tools\codex-session\analyze-latest.ps1
#    -FullTimeline 完整时间线（仅小会话）；-Index 生成最近会话总览

# 1) 分析最新一次会话（终端摘要）
codex-session-timeline --latest

# 2) 分析最新会话并导出 HTML 报告（含时间线+诊断，适合浏览器看）
codex-session-timeline --latest --html-out reports\latest.html --timeline-limit -1

# 3) 分析某个 rollout 文件
codex-session-timeline C:\Users\27648\.codex\sessions\2026\09\05\rollout-xxx.jsonl

# 4) 生成最近 20 个会话的 HTML 总览
codex-session-timeline --html-index-out reports\index.html --session-limit 20

# 5) 只看某个项目目录的会话（按 cwd 过滤）
codex-session-timeline --html-index-out reports\project.html --project-filter AI-Native-Game-Engine

# 6) 输出完整 JSON（可再加工）
codex-session-timeline <file> --json-out reports\out.json
```

## 报告能回答什么（对应"上下文工程链路有没有问题"）

- 每轮工具调用输入/输出大小、耗时、失败/超时
- 哪类调用最占时间/输出（文件读取、rg、命令执行…）
- token 用量：输入 / 缓存输入 / 输出
- 每轮瓶颈归类：工具输出过大、命令耗时、输出后分析空档、慢首动作
- 只读风险看板（红/黄/绿），提示需要人工判断的会话

## 局限与边界

- **看不到私有 reasoning**（日志中加密），只能从事件空档推断"非工具时间"。
- 它是通用 Codex 分析，**不知道本项目的 Skill/Workflow/Stage 语义**。
  要判断"Agent 有没有按我们的上下文工程链路走"，需人工或后续让 Agent 对照
  rollout 与本项目 `AGENTS.md`/Skill/计划检查差异——这一步不在本工具内。
- 本工具只读，不改 `~/.codex/sessions`，不调用外部 API。

## 日常推荐流程

```powershell
cd D:\work\AI-Native\tools\codex-session-timeline-analyzer
codex-session-timeline --latest --html-out reports\latest.html --timeline-limit -1
start reports\latest.html
```

然后人工/让 Agent 对照项目 Skill 看链路是否符合预期。

