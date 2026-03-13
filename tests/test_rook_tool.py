"""Tests for chirp_create — script generation and pin configuration."""

import pytest
from chirp.rook_tool import chirp_create, parse_pin, _to_snake


class TestParsePin:
    def test_basic(self):
        assert parse_pin("UCount:int") == ("UCount", "int")
        assert parse_pin("Intent:string") == ("Intent", "string")
        assert parse_pin("Surface:Surface") == ("Surface", "Surface")

    def test_with_spaces(self):
        assert parse_pin("U Count : int") == ("U Count", "int")

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="Pin must be"):
            parse_pin("no_colon")


class TestToSnake:
    def test_pascal_case(self):
        assert _to_snake("UCount") == "u_count"
        assert _to_snake("VCount") == "v_count"

    def test_already_snake(self):
        assert _to_snake("u_count") == "u_count"

    def test_single_word(self):
        assert _to_snake("grading") == "grading"


class TestChirpCreate:
    def test_returns_script_and_pins(self):
        result = chirp_create(
            pins_in=["SurfaceDesc:string", "Intent:string"],
            pins_out=["UCount:int", "VCount:int", "Grading:float"],
            signature="surface_desc, intent -> u_count, v_count, grading",
        )
        assert "script" in result
        assert "pins_in" in result
        assert "pins_out" in result
        assert len(result["pins_in"]) == 2
        assert len(result["pins_out"]) == 3

    def test_script_contains_signature(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["Y:int"],
            signature="x -> y",
        )
        assert 'x -> y' in result["script"]

    def test_script_contains_input_fields(self):
        result = chirp_create(
            pins_in=["SurfaceDesc:string", "Intent:string"],
            pins_out=["UCount:int"],
            signature="surface_desc, intent -> u_count",
        )
        script = result["script"]
        assert "public string SurfaceDesc" in script
        assert "public string Intent" in script

    def test_script_contains_output_fields(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["UCount:int", "Grading:float"],
            signature="x -> u_count, grading",
        )
        script = result["script"]
        assert "public int UCount" in script
        assert "public double Grading" in script

    def test_script_contains_http_call(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["Y:int"],
            signature="x -> y",
        )
        assert "localhost:9900/chirp/call" in result["script"]
        assert "HttpClient" in result["script"]

    def test_geometry_input_uses_tostring(self):
        result = chirp_create(
            pins_in=["Srf:Surface"],
            pins_out=["Count:int"],
            signature="srf -> count",
        )
        assert "ToString()" in result["script"]

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown output type"):
            chirp_create(
                pins_in=["X:string"],
                pins_out=["Y:FooBar"],
                signature="x -> y",
            )

    def test_deterministic_code_included(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["Y:int"],
            signature="x -> y",
            deterministic_code="Y = Y * 2;",
        )
        assert "Y = Y * 2;" in result["script"]
        assert "Deterministic" in result["script"]

    def test_unknown_input_type_raises(self):
        with pytest.raises(ValueError, match="Unknown input type"):
            chirp_create(
                pins_in=["X:FooBar"],
                pins_out=["Y:int"],
                signature="x -> y",
            )

    def test_geometry_output_is_string_field(self):
        """Geometry output types must be C# string fields (LLM returns text)."""
        result = chirp_create(
            pins_in=["Desc:string"],
            pins_out=["Center:Point3d"],
            signature="desc -> center",
        )
        script = result["script"]
        assert "public string Center" in script
        assert "GetString()" in script

    def test_signature_with_quotes_escaped(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["Y:int"],
            signature='given a "description" -> y',
        )
        assert r'given a \"description\" -> y' in result["script"]

    def test_pin_metadata(self):
        result = chirp_create(
            pins_in=["Surface:Surface", "Intent:string"],
            pins_out=["UCount:int"],
            signature="surface, intent -> u_count",
        )
        assert result["pins_in"][0] == {"name": "Surface", "type": "Surface"}
        assert result["pins_in"][1] == {"name": "Intent", "type": "string"}
        assert result["pins_out"][0] == {"name": "UCount", "type": "int"}
