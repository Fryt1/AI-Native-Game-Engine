# Stage Kind: Change

Use for generation, import, export, conversion, modification, repair,
optimization, configuration, migration, or publication.

## Execution checklist knowledge

- identify the target and affected scope
- read state required for the change or rollback
- verify preconditions and permissions
- state overwrite, side-effect, and recovery policy
- execute the selected operation and persist when requested

## Acceptance checklist knowledge

- required changes are observable after execution
- declared preservation items remain unchanged
- forbidden changes did not occur
- post-change state can be read independently
- no blocking Tool or host error remains

Freeze execution and acceptance checklists and check their required Tools before
the first side effect.
