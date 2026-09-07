# Adding a Reusable Workflow: Step-by-Step Guide

> 面向读者：要往项目里加一个“可复用流程”的用户/贡献者。
> 读完本文你能回答：加哪些文件、每个文件填什么、用什么命令校验/发布。
> 模板基准：`skills/ai-native-workflow-orchestration/templates/`。

## 0. 先判断类型

```text
纯编排型（不新增执行能力）→ 走 workflows/<id>/ 包即可
带新执行能力（ComfyUI 图 / 脚本）→ 额外注册 Toolset（src/ainative/toolsets/）
```

一个可执行图/脚本**不是** Workflow Definition：图是 Tool 的实现资产，应放
Toolset；Workflow 包描述“何时用、怎么用、依赖什么、怎么验收”。

## 1. 建立草稿

推荐用脚本生成草稿骨架（也可手工建目录）：

```powershell
python scripts\workflows\create_workflow.py <workflow-id>
# 生成到 artifacts/scratch/workflow-drafts/<workflow-id>/r1/
```

## 2. 补齐核心文件

一个可复用 Workflow Definition 至少含 4 个核心文件：

```text
workflows/<workflow-id>/
├── WORKFLOW.md            # 意图 / 不变式 / 输入输出契约 / 允许调用源 / 恢复
├── requirements.yaml      # requires：project_tools / mcp_tools / fixtures / host
├── plan.template.yaml     # route + profile + inputs 占位 + steps/stages/calls/checklists
└── verification/
    ├── machine-report.json  # status=passed（promote 必需）
    └── human-review.json    # status=approved | not_required（promote 必需）
```

建议再加：

```text
├── examples/         # 真实案例（输入 + 输出引用）
├── tests/            # plan schema / graph 校验测试
└── verification/README.md
```

### WORKFLOW.md 模板

```markdown
# <Workflow 名称>

Reusable Workflow Definition：<一句话目标>。

## Intent
<本工作流完成什么、不完成什么>

## Required invariants
- <不可违反的约束>

## Allowed execution sources
MCP:
    <server_id / tool_name 示例>
Project Tools:
    <toolset_id.tool_id 示例>

## Input / Output contract
<输入格式、输出产物>

## Validation
<验收方法：读回、文件存在、证据目录>

## Failure rules
<缺失依赖/OOM/结果不符时的处理>
```

### requirements.yaml 模板

```yaml
version: 1
workflow_id: <workflow-id>
requires:
  project_tools:
    - <toolset_id.tool_id>
  mcp_tools:
    - server_id: <server_id>
      tool_name: <tool_name>
  fixtures:
    - projects/fixtures/<name>
  host:
    <host>_version: ">=<version>"
```

### plan.template.yaml 模板（骨架）

```yaml
version: 1
workflow_id: <workflow-id>
route: host_operation        # host_operation | asset_transfer | artifact_pipeline
profile: default

inputs:
  <input_name>: <path/占位>

steps:
  - step_id: <step-id>
    purpose: <本步目标>
    stages:
      - stage_id: <stage-id>
        stage_kind: change    # change | investigation | planning
        purpose: <stage 目标>
        calls:
          - kind: mcp
            call_id: <call-id>
            server_id: <server>
            tool_name: <tool>
            arguments: {}
            depends_on: []
            usage: execute
        execution_checklist:
          - item_id: <item>
            description: <要处理什么>
            required: true
            call_ids: [<call-id>]
            evidence_required: true
        acceptance_checklist:
          - check_id: <check>
            description: <要证明什么>
            required: true
            call_ids: [<call-id>]
            source_call_id: <call-id>
            operator: exists    # exists|truthy|equals|tool_succeeded|set_equals|count_equals|within_tolerance
            actual_path: [<output>]
            expected: null
            tolerance: null
            evidence_required: true
```

完整 JSON 字段见 `skills/.../templates/workflow-plan-template.json` 与
`workflow-plan-schema.json`（权威结构）。

## 3. 带执行能力时：注册 Toolset

若工作流调用“项目自有图/脚本”，把它放进 Toolset 并发布成普通 Tool：

```text
src/ainative/toolsets/<toolset_id>/
├── __init__.py
└── graphs/ 或 scripts/   # 实现资产
```

复用现成包装器 `PythonScriptWorkflowProvider`
（`src/ainative/toolsets/workflow_tools/python_script.py`），或自建 provider，
通过 `toolsets()` 发布 `ToolsetDefinition`。之后 plan.template 里的 calls 可写：

```yaml
- kind: tool
  call_id: run-graph
  toolset_id: <toolset_id>
  tool_id: <toolset_id>.<operation>
  arguments: {}
  usage: execute
```

## 4. 校验草稿

```powershell
python scripts\workflows\validate_workflow.py <draft-root>
```

硬性检查（当前实现）：

```text
WORKFLOW.md 存在
requirements.yaml 存在且含 "requires:"
plan.template.yaml 存在且含 "calls:" 且含 "kind: tool" 或 "kind: mcp"
（且不含已移除的 "tool_call"）
```

## 5. 真实运行 + 机器证据

1. 在 fixtures 或真实输入上运行；
2. 把输出/证据存到 `artifacts/evidence/...`；
3. 写 `verification/machine-report.json`：

```json
{
  "status": "passed",
  "workflow": "<workflow-id>",
  "date": "YYYY-MM-DD",
  "comfyui_version": "x.y.z",
  "run": {
    "input": "<输入>",
    "outputs": ["<输出1>", "<输出2>"],
    "evidence_dir": "artifacts/evidence/<...>",
    "oom": false
  }
}
```

4. 需要人工评审时写 `human-review.json`（否则 `not_required`）。

## 6. 发布

```powershell
python scripts\workflows\promote_workflow.py <draft-root> [--replace]
```

promote 硬性要求：

```text
validate_workflow 通过
machine-report.json.status == "passed"
human-review.json.status ∈ {"approved", "not_required"}
```

发布产物拷到 `workflows/<workflow-id>/` 并写入 publication.json。

## 7. 登记

把新 Workflow 加入 `workflows/README.md` 的 Current workflows 列表（一行）。

## 常见错误

| 错误 | 后果 | 修正 |
|---|---|---|
| 缺 plan.template.yaml | validate INVALID | 按模板补 |
| plan 无 calls 或 tool/mcp | validate INVALID | 至少一个合法 call |
| 无 machine-report/human-review | promote 拒绝 | 补 verification JSON |
| route 选错（ComfyUI 输出产物误用 host_operation） | 语义偏差 | 按生命周期重判（产物→artifact_pipeline） |
| 把图 JSON 放 workflows/ 当 Definition | 双份/错层 | 图放 toolset/graphs，workflows 只放 Definition |
| 改 skill 包后不同步 integrity_gate required 列表 | gate 可能不查新文件 | 维护者手工登记 required 列表 |