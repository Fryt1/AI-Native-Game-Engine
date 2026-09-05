# UE5 Actor Fixture Project

This is the canonical small UE5 project workspace used to verify the generic
`host_operation` Workflow and UE5 Editor Python Toolset.

## Project

```text
ActorFixture.uproject
Config/DefaultEngine.ini
Content/AINativeActorE2E.umap
```

The `.umap` is the reproducible fixture input. Unreal-generated folders such as
`DerivedDataCache/`, `Intermediate/`, and `Saved/` are local editor state and
are moved to `artifacts/scratch/` after acceptance runs.

## Acceptance

From the repository root:

```powershell
python scripts\e2e\run_ue5_actor_operation_e2e.py
```

The runner launches the normal `UnrealEditor.exe` once to resolve the fixture
Level, creating it only when missing, and records native-window evidence. It
then runs the Agent/Skill/Workflow Actor mutation through
`UnrealEditor-Cmd.exe` and validates the read-back Transform.
