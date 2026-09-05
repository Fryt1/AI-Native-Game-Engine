# Toolset: Workflow Validation

## Toolset ID

```text
validation.workflow
```

## Publishers

```text
ManifestValidator
AssetsBridgeValidator
future host-specific comparison and validation Tools
```

## Current registered Tool

```text
validate
```

Complex checks such as skeleton hierarchy, animation inventory, material
bindings, or cross-host relation comparison remain normal Tools in this Toolset.
There is no second checker Registry.

A validation Tool returns structured facts and evidence. The Stage acceptance
checklist references that ExecutionResult and the deterministic evaluator records a
`CheckResult`. A successful process exit or file existence alone is not proof of
preservation or semantic completion.
