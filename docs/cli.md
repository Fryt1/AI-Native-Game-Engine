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
  "blender": {"executable": "E:/Blender/blender.exe"},
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

CLI 只解析 Registry 中的确切 Tool 并执行项目实现，不读 plan、不调度 Stage。
CLI 返回后，Agent 再把结构化结果交给 `WorkflowSession.record_execution_result()`
做 plan/Stage 校验。
