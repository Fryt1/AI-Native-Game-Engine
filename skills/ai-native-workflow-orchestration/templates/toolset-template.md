# Toolset Contract Template: <Title>

## Toolset ID

```text
<toolset.id>
```

## Owner

Describe the project Tool provider that publishes and executes the Tool functions.

## Tools

For each Tool record:

```text
tool_id
operation
description
input schema
output schema
implementation boundary
failure behavior
```

A Tool is executable code. Its implementation may call several lower-level
APIs when they form one coherent operation. The Toolset document does not
become a Workflow sequence.

## Readiness and limitations

State what must be ready, what call surfaces are used internally, and what the
Toolset does not claim.
