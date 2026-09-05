# AssetsBridge Dependency Sources

```text
vendor/assetsbridge/
├── plugin-source/   UE5 AssetsBridge plugin source/build input
└── blender-addon/   external Blender AssetsBridge Add-on source
```

The runtime reaches these through the AssetsBridge Backend's connector seams.
Generated packages are written to `artifacts/exports/`; probe output is written
to `artifacts/evidence/` or `artifacts/scratch/`.
