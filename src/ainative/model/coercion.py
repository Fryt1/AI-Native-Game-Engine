"""Coerce a plain string into its enum on a frozen dataclass.

`TaskContract.route` accepts either a `TaskRoute` or its string value, so a
hand-written task JSON behaves identically to one built in Python. Every other
enum field must behave the same way: otherwise `to_dict()` reaches
`self.field.value` and raises `AttributeError: 'str' object has no attribute
'value'` instead of working.

`reading/deserialize.py` already normalizes enums on the JSON path via its own
`_enum()` helper; this covers the direct-construction path.
"""

from __future__ import annotations

import enum
from typing import Any


def coerce_enum(instance: Any, field_name: str, enum_type: type[enum.Enum]) -> None:
    """Replace `instance.field_name` with its enum member if it is a plain value.

    Frozen dataclasses cannot assign normally, so this goes through
    `object.__setattr__`. An unknown value raises `ValueError` from the enum
    constructor, which is the desired outcome: reject, do not guess.
    """

    value = getattr(instance, field_name)
    if not isinstance(value, enum_type):
        object.__setattr__(instance, field_name, enum_type(value))
