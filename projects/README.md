# Project Workspaces

This directory contains reproducible project workspaces and source fixtures.
Generated host state is kept out of the source tree when practical and is
ignored by `.gitignore` when a host recreates it locally.

## Layout

```text
projects/
└── fixtures/
    ├── blender/       Blender source fixtures
    ├── tasks/         Task Contract fixtures
    └── ue5/           UE5 project fixtures

vendor/assetsbridge/
    external plugin and Blender Add-on sources used by the fixtures
```

## Ownership

- Put project-specific source inputs, manifests, and local notes here.
- Put generated logs, temporary Blender files, exported GLBs, and UE5 output in
  `artifacts/` or a fixture's ignored generated-state folders.
- Do not put repository-wide Agent rules here; those belong in `AGENTS.md` or
  `skills/ai-native-workflow-orchestration/`.
- Do not treat a project workspace as a Toolset Registry.

A fixture README must describe its host paths and acceptance command. The
canonical UE5 fixtures are:

```text
projects/fixtures/ue5/actor-fixture/
projects/fixtures/ue5/level-template-fixture/
```

`actor-fixture` verifies Actor host operations. `level-template-fixture`
verifies creating and opening a Level from the UE5 default lighting template.

