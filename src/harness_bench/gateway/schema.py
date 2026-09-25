"""The one shape of an answer, read from `schemas/verdict-set.v1.json` (design section 8.3 step 4).

A stdlib validator for the closed subset of JSON Schema that file uses: `type` (object, array, integer, string),
`required`, `properties`, `additionalProperties: false`, `items`, `minItems`, `enum`, `minimum`, `maxLength`. A JSON
boolean is never an integer. Beyond the file, one check depends on the rubric: the item ids are exactly 1..n, each
once (JSON Schema cannot say "unique by property"). A keyword outside the subset fails closed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "verdict-set.v1.json"
_KNOWN = {"$id", "type", "required", "properties", "additionalProperties", "items", "minItems", "enum", "minimum",
          "maxLength"}
_TYPES = {"object": dict, "array": list, "integer": int, "string": str}


def schema_sha256() -> str:
    return hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()


def _check(value: object, rule: dict, path: str, out: list[str]) -> None:
    unknown = set(rule) - _KNOWN
    if unknown:
        raise ValueError(f"schema keyword outside the validator's subset: {sorted(unknown)}")
    kind = rule.get("type")
    if kind and (isinstance(value, bool) or not isinstance(value, _TYPES[kind])):
        out.append(f"{path}: not an {kind}" if kind in ("object", "array", "integer") else f"{path}: not a {kind}")
        return
    if "enum" in rule and value not in rule["enum"]:
        out.append(f"{path}: {value!r} not in {rule['enum']}")
    if "minimum" in rule and value < rule["minimum"]:
        out.append(f"{path}: below {rule['minimum']}")
    if "maxLength" in rule and len(value) > rule["maxLength"]:
        out.append(f"{path}: longer than {rule['maxLength']}")
    if kind == "array":
        if len(value) < rule.get("minItems", 0):
            out.append(f"{path}: fewer than {rule['minItems']} items")
        for i, v in enumerate(value):
            _check(v, rule.get("items", {}), f"{path}[{i}]", out)
    if kind == "object":
        props = rule.get("properties", {})
        out += [f"{path}: {k!r} missing" for k in rule.get("required", []) if k not in value]
        if rule.get("additionalProperties") is False:
            out += [f"{path}: unexpected key {k!r}" for k in value if k not in props]
        for k, sub in props.items():
            if k in value:
                _check(value[k], sub, f"{path}.{k}", out)


def validate(answer: object, items: int) -> list[str]:
    """Every problem with `answer`, in a fixed order; [] when it is a valid verdict set for a rubric of `items`."""
    out: list[str] = []
    _check(answer, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")), "$", out)
    rows = answer.get("items") if isinstance(answer, dict) else None
    if not isinstance(rows, list):
        return out
    ids = [r["item"] for r in rows if isinstance(r, dict) and type(r.get("item")) is int]
    out += [f"$.items: item {i} repeated" for i in sorted({i for i in ids if ids.count(i) > 1})]
    out += [f"$.items: item {i} not in 1..{items}" for i in sorted(set(ids)) if i > items]
    missing = [i for i in range(1, items + 1) if i not in ids]
    if missing:
        out.append(f"$.items: items {missing} missing")
    return out
