"""Check one evidence record against the shape this guidance promises.

This is a **checker, not a generator**: it reads an Agent's evidence record and
reports what does not conform. It authors nothing and takes no side effect.

The engine declares no dependencies, so the JSON Schema subset is implemented here
rather than imported. Only the keywords `evidence.schema.json` actually uses are
supported; anything else raises, because a keyword silently skipped is a
constraint nobody enforces.

Usage:
    python scripts/check_evidence.py path/to/evidence.json
    python scripts/check_evidence.py --schema-only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "evidence.schema.json"

SUPPORTED = frozenset({
    "$schema", "$id", "$ref", "$defs", "title", "description",
    "type", "required", "properties", "additionalProperties",
    "items", "enum", "pattern", "minLength", "minimum",
})

_TYPES = {
    "object": dict, "array": list, "string": str,
    "number": (int, float), "integer": int, "boolean": bool, "null": type(None),
}


class EvidenceError(RuntimeError):
    """The record does not conform to the schema."""


def load_schema(path: Path) -> dict:
    """Read the schema, rejecting any keyword this checker cannot enforce."""

    schema = json.loads(path.read_text(encoding="utf-8"))
    unsupported: list[str] = []

    def scan(node: object, where: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"properties", "$defs"} and isinstance(value, dict):
                    for name, sub in value.items():
                        scan(sub, f"{where}/{key}/{name}")
                    continue
                if key not in SUPPORTED:
                    unsupported.append(f"{where}: {key}")
                scan(value, f"{where}/{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                scan(item, f"{where}/{index}")

    scan(schema, "#")
    if unsupported:
        raise EvidenceError(
            "the schema uses keywords this checker cannot enforce, so they would "
            "silently pass: " + ", ".join(sorted(set(unsupported))))
    return schema


def resolve(schema: dict, node: dict) -> dict:
    """Follow a local ``$ref``."""

    while "$ref" in node:
        target: object = schema
        for segment in node["$ref"][2:].split("/"):
            target = target[segment]  # type: ignore[index]
        node = target  # type: ignore[assignment]
    return node


def matches(value: object, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    python_type = _TYPES.get(expected)
    if python_type is None:
        raise EvidenceError(f"unknown type in schema: {expected!r}")
    return isinstance(value, python_type)


def check(value: object, node: dict, schema: dict, pointer: str,
          problems: list[str]) -> None:
    """Check one value against one schema node, collecting every problem."""

    node = resolve(schema, node)

    if "enum" in node and value not in node["enum"]:
        problems.append(f"{pointer}: {value!r} is not one of {node['enum']}")
        return

    if "type" in node:
        declared = node["type"]
        allowed = declared if isinstance(declared, list) else [declared]
        if not any(matches(value, name) for name in allowed):
            problems.append(
                f"{pointer}: expected {' or '.join(allowed)}, "
                f"got {type(value).__name__}")
            return

    if isinstance(value, str):
        if len(value) < node.get("minLength", 0):
            problems.append(f"{pointer}: shorter than {node['minLength']}")
        if "pattern" in node and not re.search(node["pattern"], value):
            problems.append(f"{pointer}: {value!r} does not match {node['pattern']}")

    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in node and value < node["minimum"]:
            problems.append(f"{pointer}: {value} below minimum {node['minimum']}")

    if isinstance(value, list):
        if "items" in node:
            for index, item in enumerate(value):
                check(item, node["items"], schema, f"{pointer}/{index}", problems)

    if isinstance(value, dict):
        for name in node.get("required", []):
            if name not in value:
                problems.append(f"{pointer}: missing required '{name}'")
        properties = node.get("properties", {})
        for name, sub in value.items():
            if name in properties:
                check(sub, properties[name], schema, f"{pointer}/{name}", problems)
            elif node.get("additionalProperties") is False:
                problems.append(f"{pointer}: unexpected property '{name}'")


def validate(record: object, schema: dict) -> list[str]:
    problems: list[str] = []
    check(record, schema, schema, "#", problems)
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", nargs="?", type=Path,
                        help="the evidence record to check")
    parser.add_argument("--schema-only", action="store_true",
                        help="only prove the schema is enforceable")
    args = parser.parse_args(argv)

    try:
        schema = load_schema(SCHEMA_PATH)
    except (OSError, json.JSONDecodeError, EvidenceError) as exc:
        print(f"schema unusable: {exc}")
        return 2

    if args.schema_only:
        print("schema is enforceable: every keyword it uses is implemented")
        return 0

    if args.record is None:
        print("no record given; pass a path or --schema-only")
        return 2

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"record unreadable: {exc}")
        return 2

    problems = validate(record, schema)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"{len(problems)} problem(s)")
        return 1

    print("record conforms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
