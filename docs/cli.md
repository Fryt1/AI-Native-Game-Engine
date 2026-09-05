# Project Tool CLI

项目自有的 Tool（注册在 Project Tool Registry）暴露进程级 CLI，Agent 可直接调用；Blender MCP / UE5 MCP 不经过此 CLI，仍配置在 Agent 上。

## 运行

```powershell
# 方式一：源码在 PYTHONPATH 上
$env:PYTHONPATH='D:\work\AI-Native-Game-Engine\src'
python -m ainative.tools --help

# 方式二：安装后使用 console script
pip install -e .
ainative-tools --help
```

## 运行配置（runtime.json）

这不是 MCP 配置，只是说明本机哪些 host/实现可用：

```json
{
  "blender": {"executable": "E:/blender/blender.exe"},
  "ue5": {
    "executable": "D:/UnrealEngine/ue5.7.1/UnrealEngine/Engine/Binaries/Win64/UnrealEditor-Cmd.exe",
    "project": "D:/project/Game.uproject",
    "script": "D:/work/AI-Native-Game-Engine/src/ainative/toolsets/ue5_editor/execution/bridge_entry.py",
    "launch_mode": "commandlet"
  },
  "assetsbridge": {"directory": "D:/bridge"}
}
```

## 调用一个 Tool

```powershell
python -m ainative.tools --config runtime.json --toolset blender.editor --operation set-location --args '{"location":[1,2,3]}'
python -m ainative.tools --config runtime.json --task task.json --toolset transfer.assetsbridge --tool transfer.assetsbridge.transfer_to_edit_host
```

输出一个结构化 `ExecutionResult`（JSON）。退出码仅当状态为
`succeeded`/`degraded` 时为 0。

### 运行语义与安全边界

- CLI 只执行调用方明确选择的 `ToolCall`，不会替 Agent 选择具体 Tool。
- 如果传入 `--task`，CLI 会重新计算 Task 的 Route/Workflow 选择，并把
  Backend、Host 和 Blender call surface 传给执行层；这对 Direct Transfer 很重要。
- 配置了 `ue5` 时，AssetsBridge 使用真实的 `UnrealEditorPythonExecutor`。
  没有 `ue5` 时必须显式设置 `"protocol_only": true`，这才会启用协议文件
  测试模式；该模式不执行真实 UE5 资产导入/导出。
- 如果 Task 带有 AssetsBridge，CLI 会按 task id 使用独立交换目录；同一个
  逻辑 task 的多个阶段仍共享该目录，避免不同 task 互相污染。
- 交换 JSON 使用原子写入；结果文件会在执行前清理，旧结果、错误状态、超时
  和非法 JSON 都会返回结构化 `blocked`/`failed` 结果。


CLI 只解析 Registry 中的确切 Tool 并执行项目实现，不读 plan、不调度 Stage。
CLI 返回后，Agent 再把结构化结果交给 `WorkflowSession.record_execution_result()`
做 plan/Stage 校验。
