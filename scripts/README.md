# Project Scripts

Operational and test scripts for the AI Native Game Engine.

They are not runtime Python packages; they call the Toolset implementations under `src/ainative/toolsets/`.

## Layout

```text
scripts/
├── agent/        Skill/Workflow inspection entry point
├── build/        packaging helpers
├── docs/         command/API operational docs
├── e2e/          host-driven end-to-end workflows (UE5/Blender/AssetsBridge)
├── fixtures/     runner fixtures
├── preflight/    unified read-only dependency preflight (run_preflight.py)
├── probes/       read-only host probes
├── trace/        AgentTrace JSONL analysis
└── workflows/    Workflow Definition lifecycle helpers
```

## Run

Execute from the repository root:

```powershell
python scripts/e2e/ue5/run_actor_operation_e2e.py --timeout 120
python scripts/trace/analyze_trace.py <run-id-or-path>
```

## Preflight

Before a Workflow with host/MCP requirements runs, verify the machine:

```powershell
python scripts\preflight\run_preflight.py --workflow-root workflows\blender-ue5-asset-roundtrip --config artifacts\scratch\preflight.local.json --json
```

Local host paths/endpoints belong in a machine-local JSON config (see `preflight.example.json`);
preflight is read-only and never starts UE5 or Blender.

## Maintain

- Scripts should not duplicate Toolset logic. Import from `ainative` when possible.
- Probe/e2e outputs belong under `artifacts/evidence/` or `artifacts/scratch/`, never next to source.
- Keep each script's operational contract in `scripts/docs/` when it changes.

## License

MIT © [Fry](https://github.com/Fryt1). See [LICENSE](../LICENSE).
