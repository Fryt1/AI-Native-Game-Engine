# Direct Transfer Backend

Direct Transfer uses exchange files such as GLB, FBX, or USD and native host
Import operations.

```text
Direct Transfer Backend
    → exchange file
    → target native Import
    → Loss Report
```

It is valid when the Task Contract accepts file-level loss. It must not claim
that UE5 Asset Path, object identity, Material Graph, or Reimport semantics were
preserved without evidence.
