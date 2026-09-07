# Operational Tool Documentation

Command-level documentation for scripts whose exact behavior must stay separate from Agent rules.

Documents exact tool behavior. Separate from `SKILL.md` and Workflow prose so command details can change without changing the Agent's high-level rules.

## What belongs here

- executable paths and launch modes
- command-line flags
- environment variables
- input and result-file contracts
- process readiness and timeout behavior
- known tool errors and recovery actions

## What does not belong here

- selecting a Workflow
- defining business intent
- deciding preservation policy
- replacing a Stage Contract

## Current tools

- [`blender-cli.md`](blender-cli.md)
- [`ue5-python.md`](ue5-python.md)
- [`assetsbridge-json.md`](assetsbridge-json.md)

## License

MIT © [Fry](https://github.com/Fryt1). See [LICENSE](../../../../LICENSE).
