"""The subset of JSON Schema that ergon contracts use.

Written here instead of depending on a package: contracts stay small, and ergon stays free of dependencies.
Supported: type, const, enum, oneOf, required, properties, additionalProperties: false, minLength, maxLength,
pattern, items, minItems, maxItems.
"""
import json
import re
from pathlib import Path

_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool}


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def errors(value, schema: dict, path: str = "$") -> list[str]:
    if "oneOf" in schema:
        if sum(1 for option in schema["oneOf"] if not errors(value, option, path)) != 1:
            return [f"{path}: must match exactly one of {len(schema['oneOf'])} allowed shapes"]
        return []
    kind = schema.get("type")
    if kind and (not isinstance(value, _TYPES[kind]) or (kind == "integer" and isinstance(value, bool))):
        return [f"{path}: expected {kind}"]
    out = []
    if "const" in schema and value != schema["const"]:
        out.append(f"{path}: must be {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{path}: must be one of {schema['enum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            out.append(f"{path}: shorter than {schema['minLength']} characters")
        if len(value) > schema.get("maxLength", float("inf")):
            out.append(f"{path}: longer than {schema['maxLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            out.append(f"{path}: does not match {schema['pattern']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            out.append(f"{path}: fewer than {schema['minItems']} items")
        if len(value) > schema.get("maxItems", float("inf")):
            out.append(f"{path}: more than {schema['maxItems']} items")
        for i, element in enumerate(value):
            out += errors(element, schema.get("items", {}), f"{path}[{i}]")
    if isinstance(value, dict):
        out += [f"{path}: missing {key!r}" for key in schema.get("required", []) if key not in value]
        props = schema.get("properties", {})
        for key, element in value.items():
            if key in props:
                out += errors(element, props[key], f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                out.append(f"{path}: unexpected field {key!r}")
    return out
