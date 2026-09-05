# UE5 Level Template Fixture

This fixture verifies the `host_operation` Level provisioning Stage without
using image or window inspection as the operation result.

## Source

```text
LevelTemplateFixture.uproject
Config/DefaultEngine.ini
```

The target Level is generated under `Content/` by the acceptance runner and is
not a source fixture. Generated Unreal state remains ignored by the repository
layout rules.

## Acceptance

From the repository root:

```powershell
python scripts\e2e\run_ue5_level_template_e2e.py
```

The runner uses the registered UE5 Editor Toolset to create or explicitly
reuse `/Game/DefaultLightingLevel` from
`/Engine/Maps/Templates/Template_Default`, load it, verify default lighting
objects through the UE5 API, save it, and independently read it back.
