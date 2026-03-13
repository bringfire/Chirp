"""Tests for type resolution and Pydantic model building."""

import pytest
from chirp.types import resolve_type, build_output_model


class TestResolveType:
    def test_primitives(self):
        assert resolve_type("int") is int
        assert resolve_type("float") is float
        assert resolve_type("string") is str
        assert resolve_type("str") is str
        assert resolve_type("bool") is bool

    def test_list_types(self):
        assert resolve_type("list[int]") == list[int]
        assert resolve_type("list[float]") == list[float]
        assert resolve_type("list[str]") == list[str]

    def test_gh_geometry_types_resolve_to_str(self):
        for t in ["Point3d", "Surface", "Mesh", "Curve", "Brep", "Plane"]:
            assert resolve_type(t) is str

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown type"):
            resolve_type("FooBar")


class TestBuildOutputModel:
    def test_simple_schema(self):
        model = build_output_model({"count": "int", "label": "string"})
        instance = model(count=42, label="hello")
        assert instance.count == 42
        assert instance.label == "hello"

    def test_coerces_on_validation(self):
        model = build_output_model({"value": "float"})
        instance = model(value="3.14")
        assert instance.value == 3.14

    def test_mixed_schema(self):
        model = build_output_model({
            "u_count": "int",
            "v_count": "int",
            "grading": "float",
            "description": "Surface",
        })
        instance = model(u_count=5, v_count=10, grading=0.8, description="planar surface")
        assert instance.u_count == 5
        assert instance.description == "planar surface"
