# Project Workspaces

Reproducible project workspaces and source fixtures used by tests and host acceptance runs.

## Layout

```text
projects/
└── fixtures/
    ├── blender/   Blender source fixtures
    ├── tasks/     Task Contract fixtures
    └── ue5/       UE5 project fixtures
```

External AssetsBridge plugin and Blender Add-on sources are vendored under `vendor/assetsbridge/`.

## Rules

- Keep project-specific source inputs and manifests here.
- Put generated logs, temporary Blender files, exported GLBs, and UE5 output under `artifacts/` or a fixture's ignored generated-state folders.
- Do not put repository-wide Agent rules here; those belong in `AGENTS.md` or `skills/ai-native-workflow-orchestration/`.

## License

MIT © [Fry](https://github.com/Fryt1). See [LICENSE](../LICENSE).
