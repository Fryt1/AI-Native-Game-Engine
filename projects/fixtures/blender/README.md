# Blender Fixtures

Reproducible Blender source files used by Direct Transfer and AssetsBridge tests.

Current fixture:

```text
projects/fixtures/blender/real-cli-glb/asset.glb
```

The fixture directory also holds the `source.blend` and the `create.json`/`export.json` request files used to reproduce it.

## Acceptance

The real-Blender integration tests use `BLENDER_EXECUTABLE` (default `E:\blender\blender.exe`). See `tests/integration/blender/` and `tests/integration/transfer/`.

## License

MIT © [Fry](https://github.com/Fryt1). See [LICENSE](../../../LICENSE).
