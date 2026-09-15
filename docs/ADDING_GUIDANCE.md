# Adding a Reusable Workflow: Step-by-Step Guide

> 面向读者：要往 Skill 里加一份“可复用流程指引”的用户/贡献者。
> 读完本文你能回答：加哪些文件、每个文件填什么、怎么验收。

## 0. 先判断类型

```text
本仓库的 Workflow 指引只管：何时用、怎么用、保留什么不变式、怎么验收。
执行能力不在这里实现——宿主调用走 Agent 自己的 MCP client。
```

一份可复用的 Workflow 指引就是一个 Markdown 文件，写在 `guidance/<name>.md`。
它给 Agent 的是宏观生命周期与不变式，不是固定 Step 序列，也不含 Workflow 骨架。

**本仓库没有“配方包”这个概念。** 不存在 `recipes/`，不存在每份指引自己的
`WORKFLOW.md` / `tests/` / `verification/` 目录，也不存在按
host/object/operation 组合维护的图或脚本。宿主与模型的版本前置条件一律声明在
`docs/DEPENDENCIES.md`，不写在指引里。

## 1. 建立或更新文件

```text
guidance/<name>.md      生命周期指引：目的 / 宏观流程 / 不变式 / 完成条件 / 失败恢复
```

起稿时按下面的骨架写，再按需增删小节。指引里要写：

- 这段生命周期**何时**适用、**不**覆盖什么；
- 哪些阶段是必需的、可选的、可合并的（写“阶段目标”，不写“第几步调哪个工具”）；
- 每个 Stage 各自冻结 execution / acceptance checklist；
- 完成条件与需要的证据；
- 失败时是重试、补偿、补证据、等人工，还是由 Agent 写替换版计划。

骨架：

```text
# Workflow Guidance: <name>

## Purpose
这个生命周期拥有什么、不覆盖什么

## Recommended macro flow
<phase A> → <phase B> → <phase C>
哪些阶段必需、可选、有条件、可合并

## Complete when
完成条件与需要的证据
```

指引中不要写死 MCP tool 名。具体调用由 Agent 针对当前任务选择并写进 Workflow，
本仓库不解析 `target`。

## 2. 声明宿主依赖

指引文件**不承担依赖声明**。它要用到的宿主能力、版本下限、MCP Server 前置条件
写在 `docs/DEPENDENCIES.md` 对应小节；本仓库不实现这些调用，也不代 Agent 检查
宿主——Agent 用自己的 MCP client 在选调用之前确认目标 MCP Server 正在运行且可达
（工具列举或一次 trivial read 即可证明）。

若指引需要一个真实的图或脚本作为输入（例如 ComfyUI 图），那是 Agent 在任务里
自己准备并调用宿主 MCP 的事，不作为仓库内的数据文件。

## 3. 真实运行 + 机器证据

1. 用真实任务跑一遍这条生命周期；
2. 把结果与证据存到 `artifacts/evidence/<...>`；
3. 需要复现时，记录能说明“确实跑过”的最小事实（宿主/MCP 版本、输入、输出路径、
   是否 OOM）。本仓库不规定每个指引必须有 `verification/` 目录——证据放
   `artifacts/evidence/`，结论写进 `docs/VALIDATION_REPORT.md`。

## 4. 登记

1. 把新文件加入 `guidance/index.md` 的清单；
2. 把新文件加入 `integrity_gate.py` 的 required 列表（维护者手工登记）。

## 常见错误

| 错误 | 后果 | 修正 |
|---|---|---|
| 指引里写死 MCP tool 名 | 与“Agent 选调用”的边界冲突，工具改名即失效 | 只写 server 与不变式，调用留给 Workflow |
| 把版本前置条件写在指引里 | 依赖声明分裂成两处 | 统一写进 `docs/DEPENDENCIES.md` |
| 为每个 host/object/operation 组合新建指引 | 文档爆炸，且与 SKILL.md 的组合规则重复 | 一份指引覆盖一条宏观生命周期 |
| 改 Skill 后不同步 `integrity_gate.py` 的 required 列表 | gate 可能不查新文件 | 维护者手工登记 required 列表 |
