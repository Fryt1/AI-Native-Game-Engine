# UE5 Fixtures

```text
ue5/
├── actor-fixture/       generic UE5 Actor host-operation project
├── level-template-fixture/  default-level template fixture
└── assetsbridge-smoke/  UE5 AssetsBridge round-trip project
```

Keep `.uproject`, `Config/`, `Content/`, `Plugins/`, and fixture source here. `DerivedDataCache/`, `Intermediate/`, `Saved/`, and similar folders are generated editor state and stay ignored.

## MCP boundary

These fixture projects do not vendor Epic's engine-level ModelContextProtocol plugin and do
not start a permanent live MCP Editor. They are used by the repository's Project Tool and E2E
paths. For a live UE5 McpCall, install/enable the MCP plugin in the target UE5 project and
configure the Agent MCP Client according to [the dependency contract](../../../docs/DEPENDENCIES.md) (UE5 section).
