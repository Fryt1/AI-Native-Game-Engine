"""Check a document against the JSON Schema that defines a Workflow.

The schema is the definition of the data structure; this is the script that checks
a document against it. The engine declares no dependencies, so this implements the
subset of JSON Schema the schema actually uses rather than importing a library.

Supported: ``$ref`` (into ``$defs``), ``type``, ``required``, ``properties``,
``additionalProperties``, ``items``, ``enum``, ``const``, ``pattern``,
``minLength``, ``maxLength``, ``minimum``, ``minItems``, ``oneOf``, ``description``.

Anything outside that subset raises rather than being ignored: a keyword silently
skipped is a constraint nobody enforces, which is worse than a missing one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Keywords this checker understands. A schema using anything else is rejected.
SUPPORTED_KEYWORDS = frozenset({
    "$schema", "$id", "$ref", "$defs", "title", "description",
    "type", "required", "properties", "additionalProperties", "items",
    "enum", "const", "pattern", "minLength", "maxLength", "minimum",
    "minItems", "oneOf", "default",
})

#: Keywords carried alongside ``$ref`` that do not constrain anything, so
#: discarding them changes no verdict. Anything else next to a ``$ref`` would be
#: silently dropped by ``_resolve``, which turns a constraint into no constraint.
_ANNOTATION_KEYWORDS = frozenset({"title", "description"})

_TYPE_NAMES = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


@dataclass(frozen=True, slots=True)
class SchemaViolation:
    """One place a document departs from the schema."""

    pointer: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"pointer": self.pointer, "message": self.message}


class SchemaError(RuntimeError):
    """The document does not conform to the schema."""

    def __init__(self, violations: tuple[SchemaViolation, ...]) -> None:
        self.violations = violations
        super().__init__("; ".join(f"{v.pointer}: {v.message}" for v in violations))


def load_schema(path: Path | str) -> dict:
    """Read a schema document, rejecting keywords the checker cannot enforce."""

    schema = json.loads(Path(path).read_text(encoding="utf-8"))
    unsupported: list[str] = []
    shadowed: list[str] = []

    def scan(node: Any, where: str) -> None:
        if isinstance(node, dict):
            if "$ref" in node:
                # `_resolve` returns the target and discards every sibling. A
                # sibling annotation is fine; a sibling CONSTRAINT would be
                # dropped without a word, and a schema constraint that nothing
                # enforces is worse than one that is absent, because the spec
                # still reads as if it were checked.
                stray = sorted(set(node) - {"$ref"} - _ANNOTATION_KEYWORDS)
                if stray:
                    shadowed.append(f"{where}: {', '.join(stray)}")
            for key, value in node.items():
                if key in {"properties", "$defs"} and isinstance(value, dict):
                    for name, sub in value.items():
                        scan(sub, f"{where}/{key}/{name}")
                    continue
                if key not in SUPPORTED_KEYWORDS:
                    unsupported.append(f"{where}: {key}")
                scan(value, f"{where}/{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                scan(item, f"{where}/{index}")

    scan(schema, "#")
    if shadowed:
        raise ValueError(
            "the schema puts constraint keywords beside a $ref, where they would "
            "be discarded without being enforced: " + ", ".join(sorted(set(shadowed))))
    if unsupported:
        raise ValueError(
            "the schema uses keywords this checker cannot enforce, so they would "
            "silently pass: " + ", ".join(sorted(set(unsupported))))
    return schema


def validate(document: Any, schema: dict) -> None:
    """Raise :class:`SchemaError` when the document does not conform."""

    violations: list[SchemaViolation] = []
    _check(document, schema, schema, "#", violations)
    if violations:
        raise SchemaError(tuple(violations))


def is_valid(document: Any, schema: dict) -> bool:
    """Return True when the document conforms. Convenience for tests."""

    try:
        validate(document, schema)
    except SchemaError:
        return False
    return True


# --------------------------------------------------------------------------- #
# The checker
# --------------------------------------------------------------------------- #


def _resolve(schema: dict, root: dict, node: Any) -> Any:
    """Follow a local ``$ref``, or return the node unchanged."""

    seen = 0
    while isinstance(node, dict) and "$ref" in node:
        reference = node["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#/"):
            raise ValueError(f"only local $ref is supported, got {reference!r}")
        target: Any = root
        for segment in reference[2:].split("/"):
            if not isinstance(target, dict) or segment not in target:
                raise ValueError(f"$ref does not resolve: {reference}")
            target = target[segment]
        node = target
        seen += 1
        if seen > 32:
            raise ValueError(f"$ref chain too deep at {reference}")
    return node


def _type_of(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "integer":
        # A bool is an int in Python; a schema that says integer does not mean it.
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    python_type = _TYPE_NAMES.get(expected)
    if python_type is None:
        raise ValueError(f"unknown type in schema: {expected!r}")
    return isinstance(value, python_type)


def _check(value: Any, node: Any, root: dict, pointer: str,
           violations: list[SchemaViolation]) -> None:
    """Check one value against one schema node, appending every violation."""

    node = _resolve(root, root, node)
    if not isinstance(node, dict):
        return

    if "const" in node and value != node["const"]:
        violations.append(SchemaViolation(
            pointer, f"expected the constant {node['const']!r}, got {value!r}"))
        return

    if "enum" in node and value not in node["enum"]:
        violations.append(SchemaViolation(
            pointer, f"{value!r} is not one of {node['enum']}"))
        return

    if "type" in node:
        declared = node["type"]
        allowed = declared if isinstance(declared, list) else [declared]
        if not any(_matches_type(value, name) for name in allowed):
            violations.append(SchemaViolation(
                pointer,
                f"expected {' or '.join(allowed)}, got {_type_of(value)}"))
            return

    if "oneOf" in node:
        branch_probes: list[list[SchemaViolation]] = []
        for branch in node["oneOf"]:
            probe: list[SchemaViolation] = []
            _check(value, branch, root, pointer, probe)
            branch_probes.append(probe)
        matches = sum(1 for probe in branch_probes if not probe)

        if matches == 0:
            # "matched 0 of 2 alternatives" names no cause: the author is sent
            # looking at the discriminator when the real fault is often a field
            # shared by every branch, such as an illegal node_id.
            #
            # When some fault is common to every branch, report ONLY those. They are
            # the faults no branch can excuse, and they are the actionable ones: the
            # per-branch complaints of a branch that never applied ("expected the
            # constant 'stage'") are noise that buries the real cause.
            #
            # With no common fault, report the branch the document was actually
            # trying to be. A discriminated union says which one that is: the
            # branch whose discriminator const equals the value. Falling back on
            # "got furthest" instead reported the wrong branch, and told an author
            # who wrote kind "workflow" that 'stage' was expected -- while the
            # fault that mattered, a missing 'children', never appeared.
            common = _common_violations(branch_probes)
            discriminating = _branch_for_discriminator(node["oneOf"], root, value, branch_probes)
            reported = common or discriminating or max(
                branch_probes, key=_depth_reached, default=[])
            violations.append(SchemaViolation(
                pointer,
                f"matches no alternative of {len(node['oneOf'])}"
                + (f"; {len(common)} fault(s) are common to every alternative"
                   if common else "")))
            violations.extend(reported)
            return

        if matches > 1:
            violations.append(SchemaViolation(
                pointer,
                f"matches {matches} of {len(node['oneOf'])} alternatives, which "
                f"must be mutually exclusive"))
            return

    if isinstance(value, str):
        if "minLength" in node and len(value) < node["minLength"]:
            violations.append(SchemaViolation(
                pointer, f"shorter than {node['minLength']} characters"))
        if "maxLength" in node and len(value) > node["maxLength"]:
            violations.append(SchemaViolation(
                pointer, f"longer than {node['maxLength']} characters"))
        if "pattern" in node and not re.search(node["pattern"], value):
            violations.append(SchemaViolation(
                pointer, f"{value!r} does not match {node['pattern']}"))

    numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
    if "minimum" in node and numeric and value < node["minimum"]:
        violations.append(SchemaViolation(
            pointer, f"{value} is below the minimum {node['minimum']}"))

    if isinstance(value, list):
        if "minItems" in node and len(value) < node["minItems"]:
            violations.append(SchemaViolation(
                pointer, f"needs at least {node['minItems']} item(s), has {len(value)}"))
        if "items" in node:
            for index, item in enumerate(value):
                _check(item, node["items"], root, f"{pointer}/{index}", violations)

    if isinstance(value, dict):
        for name in node.get("required", []):
            if name not in value:
                violations.append(SchemaViolation(pointer, f"missing required '{name}'"))

        properties = node.get("properties", {})
        for name, sub in value.items():
            if name in properties:
                _check(sub, properties[name], root, f"{pointer}/{name}", violations)
            elif node.get("additionalProperties") is False:
                violations.append(SchemaViolation(
                    pointer, f"unexpected property '{name}'"))


def is_valid_against(value: Any, node: Any, root: dict) -> bool:
    """Return True when a value matches one schema node, used for ``oneOf``."""

    probe: list[SchemaViolation] = []
    _check(value, node, root, "#", probe)
    return not probe


def _branch_for_discriminator(
    branches: list[dict],
    root: dict,
    value: Any,
    probes: list[list[SchemaViolation]],
) -> list[SchemaViolation]:
    """Return the violations of the branch the value was trying to match.

    A discriminated union marks its branches with a ``const`` on one property.
    When the value carries that property with a matching value, the branch that
    declares it is the only one whose complaints are about the document rather
    than about the discriminator, so it is the one worth reporting.

    @returns that branch's violations, or an empty list when no branch claims the
        value -- in which case the caller falls back to another heuristic.
    """

    for branch in branches:
        resolved = _resolve(root, root, branch)
        if not isinstance(resolved, dict):
            continue
        for name, node in (resolved.get("properties") or {}).items():
            constant = _resolve(root, root, node)
            if not isinstance(constant, dict) or "const" not in constant:
                continue
            if isinstance(value, dict) and value.get(name) == constant["const"]:
                index = branches.index(branch)
                if index < len(probes):
                    return probes[index]
    return []


def _common_violations(probes: list[list[SchemaViolation]]) -> list[SchemaViolation]:
    """Return the violations present in every probe, deduplicated by location.

    These are the faults no branch can excuse, which is what an author needs to
    see when every branch failed.
    """

    if not probes:
        return []

    def key(violation: SchemaViolation) -> tuple[str, str]:
        return (violation.pointer, violation.message)

    shared = {key(v) for v in probes[0]}
    for probe in probes[1:]:
        shared &= {key(v) for v in probe}

    seen: set[tuple[str, str]] = set()
    out: list[SchemaViolation] = []
    for probe in probes:
        for violation in probe:
            marker = key(violation)
            if marker in shared and marker not in seen:
                seen.add(marker)
                out.append(violation)
    return out


def _depth_reached(probe: list[SchemaViolation]) -> int:
    """Return how deep into the document a branch's violations reached.

    A branch that fails on the discriminator reports at the node itself; a branch
    that got past it reports on a field inside. Depth is the pointer's segment
    count, so the deeper branch is the one whose complaints are worth reading.
    """

    return max((v.pointer.count("/") for v in probe), default=0)


def _merge_unique(*groups: list[SchemaViolation]) -> list[SchemaViolation]:
    """Concatenate violation lists, keeping the first of each location+message."""

    seen: set[tuple[str, str]] = set()
    out: list[SchemaViolation] = []
    for group in groups:
        for violation in group:
            marker = (violation.pointer, violation.message)
            if marker not in seen:
                seen.add(marker)
                out.append(violation)
    return out
