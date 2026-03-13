"""Type mapping from schema strings to Python/Pydantic types."""

from __future__ import annotations

import typing
from pydantic import BaseModel, create_model


# Schema string → Python type
TYPE_MAP: dict[str, type] = {
    "int": int,
    "float": float,
    "string": str,
    "str": str,
    "bool": bool,
    "list": list,
    "list[int]": list[int],
    "list[float]": list[float],
    "list[str]": list[str],
    "list[bool]": list[bool],
    "dict": dict,
}

# GH geometry types — passed as descriptive strings to/from the LLM.
# The script component reconstructs actual geometry from these strings.
GH_GEOMETRY_TYPES = {
    "Point3d", "Vector3d", "Plane", "Line", "Curve", "Surface",
    "Brep", "Mesh", "Box", "Circle", "Arc", "Polyline",
}


def resolve_type(type_str: str) -> type:
    """Resolve a schema type string to a Python type.

    GH geometry types resolve to str (descriptive text for LLM,
    string representation for script component to reconstruct).
    """
    if type_str in TYPE_MAP:
        return TYPE_MAP[type_str]
    if type_str in GH_GEOMETRY_TYPES:
        return str
    # Try list[T] pattern
    if type_str.startswith("list[") and type_str.endswith("]"):
        inner = type_str[5:-1]
        inner_type = resolve_type(inner)
        return list[inner_type]
    raise ValueError(f"Unknown type: {type_str!r}")


def build_output_model(schema: dict[str, str]) -> type[BaseModel]:
    """Build a Pydantic model from a schema dict.

    Args:
        schema: Mapping of field name → type string.
               e.g. {"count": "int", "label": "string", "values": "list[float]"}

    Returns:
        A Pydantic BaseModel subclass with the specified fields.
    """
    fields = {}
    for name, type_str in schema.items():
        python_type = resolve_type(type_str)
        fields[name] = (python_type, ...)
    return create_model("ChirpOutput", **fields)
