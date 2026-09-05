# Direct Transfer Toolset

## Toolset ID

```text
transfer.direct
```

This package owns file-level exchange through `backend.py` and
`filesystem.py`. Its loss model is explicit: it must not claim identity,
relation, or reimport preservation without evidence.
