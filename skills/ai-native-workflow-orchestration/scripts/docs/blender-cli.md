# Blender CLI Operational Contract

## Surfaces

```text
blender.editor Toolset
    CLI + Python or Add-on execution invoked from a Blender process
```

Use explicit absolute file paths for `.blend`, exchange artifacts, and result
files. Every operation must write a machine-readable result containing status,
operation, warnings, errors, and output references.

## Readiness

The Blender executable, the requested script, and all input artifacts must be
ready before a Stage starts. A timeout is a failed Stage with a resume pointer;
it is not a reason to switch Call Surface silently.
