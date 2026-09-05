# Project Scripts

Scripts are operational entrypoints, probes, fixture generators, and build
commands. Concrete Tool implementations live under
`D:\work\AI-Native-Game-Engine\src\ainative\toolsets\`; scripts call those
implementations or launch host processes but do not redefine the architecture.

## Layout

```text
D:\work\AI-Native-Game-Engine\scripts\
├── agent\       Agent/Skill inspection commands
├── e2e\
│   ├── ue5\     UE5 real-host runners
│   ├── blender\ Blender real-host runners
│   ├── transfer\ AssetsBridge/Direct transfer runners
│   └── support\ deterministic Agent plan fixtures
├── probes\
│   ├── ue5\
│   ├── blender\
│   └── assetsbridge\
├── fixtures\    fixture generators
└── build\       build/package commands
```

## Commands

```powershell
Set-Location D:\work\AI-Native-Game-Engine

python scripts\agent\run_agent.py projects\fixtures\tasks\task-cross-host.json --plan-only
python scripts\workflows\create_workflow.py my-workflow
python scripts\workflows\validate_workflow.py workflows\blender-ue5-asset-roundtrip --json
python scripts\probes\blender\probe_blender.py
python scripts\probes\ue5\probe_ue5.py
python scripts\probes\assetsbridge\probe_assetsbridge.py <bridge-dir> --ue5-plugin <plugin-dir> --blender-addon <addon-dir>

python scripts\e2e\blender\real_blender_bpy_smoke.py
python scripts\e2e\transfer\run_bridge_smoke.py
python scripts\e2e\transfer\run_real_assetsbridge_roundtrip.py
python scripts\e2e\ue5\run_actor_operation_e2e.py
python scripts\e2e\ue5\run_level_template_e2e.py
python scripts\e2e\transfer\run_visible_ue5_assetsbridge_e2e.py --uproject D:\path\to\Project.uproject
```

The Skill integrity command remains under the Skill package:

```powershell
python skills\ai-native-workflow-orchestration\scripts\integrity_gate.py --json
```

Temporary output goes under `artifacts\scratch\`; reportable output goes under
`artifacts\evidence\`; old runs belong under `artifacts\archive\`.
