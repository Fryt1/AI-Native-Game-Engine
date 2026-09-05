# Artifacts

Generated data separated by lifecycle:

```text
artifacts/
├── evidence/  stable acceptance evidence referenced by reports
├── exports/   generated packages and exports
├── scratch/   temporary current-run output
├── runs/      empty scratch-run entry point
└── archive/   historical runs and obsolete previews
```

Only `evidence/` is a current source of verification claims. Do not use an archived run as the current result without re-running or explicitly promoting it.

The directory stays git-ignored except placeholder `README.md`/`.gitkeep` files.
