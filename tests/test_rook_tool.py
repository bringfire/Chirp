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
            category="planner",
        )
        assert "script" in result
        assert "pins_in" in result
        assert "pins_out" in result
        # 2 user pins + auto-added Correction
        assert len(result["pins_in"]) == 3
        # 3 user pins + auto-added Reasoning
        assert len(result["pins_out"]) == 4

    def test_script_contains_signature(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["Y:int"],
            signature="x -> y",
            category="planner",
        )
        assert 'x -> y' in result["script"]

    def test_script_contains_input_fields(self):
        result = chirp_create(
            pins_in=["SurfaceDesc:string", "Intent:string"],
            pins_out=["UCount:int"],
            signature="surface_desc, intent -> u_count",
            category="planner",
        )
        script = result["script"]
        assert '"surface_desc"' in script
        assert '"intent"' in script

    def test_script_contains_output_fields(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["UCount:int", "Grading:float"],
            signature="x -> u_count, grading",
            category="planner",
        )
        script = result["script"]
        assert "ReadInt(" in script
        assert "ReadDouble(" in script

    def test_script_contains_http_call(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["Y:int"],
            signature="x -> y",
            category="planner",
        )
        assert "localhost:9900/chirp/call" in result["script"]
        assert "HttpClient" in result["script"]

    def test_geometry_input_uses_tostring(self):
        result = chirp_create(
            pins_in=["Srf:Surface"],
            pins_out=["Count:int"],
            signature="srf -> count",
            category="planner",
        )
        assert "ToString()" in result["script"]

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown output type"):
            chirp_create(
                pins_in=["X:string"],
                pins_out=["Y:FooBar"],
                signature="x -> y",
                category="planner",
            )

    def test_deterministic_code_included(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["Y:int"],
            signature="x -> y",
            category="planner",
            deterministic_code="Y = Y * 2;",
        )
        assert "Y = Y * 2;" in result["script"]
        assert "Deterministic" in result["script"]

    def test_deterministic_only_omits_llm_http_call(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["Y:string"],
            signature="x -> y",
            category="planner",
            deterministic_code='Y = X?.ToString() ?? "";',
            deterministic_only=True,
        )

        assert result["deterministic_only"] is True
        assert "/chirp/call" not in result["script"]
        assert "HttpClient" not in result["script"]
        assert "System.Net.Http" not in result["script"]
        assert 'Y = X?.ToString() ?? "";' in result["script"]
        assert 'Reasoning = (object)"deterministic";' in result["script"]

    def test_deterministic_only_avoids_json_assembly_dependency(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["Y:string"],
            signature="x -> y",
            category="planner",
            deterministic_code='Y = X?.ToString() ?? "";',
            deterministic_only=True,
        )

        script = result["script"]
        assert "System.Text.Json" not in script
        assert "JsonSerializer" not in script
        assert "JsonDocument" not in script

    def test_generated_script_avoids_system_text_json_dependency(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["Y:int", "Reason:string"],
            signature="x -> y, reason",
            category="planner",
        )

        script = result["script"]
        assert "System.Text.Json" not in script
        assert "JsonSerializer" not in script
        assert "JsonDocument" not in script
        assert "localhost:9900/chirp/call" in script
        assert "HttpClient" in script

    def test_deterministic_only_requires_code(self):
        with pytest.raises(ValueError, match="deterministic_only requires deterministic_code"):
            chirp_create(
                pins_in=["X:string"],
                pins_out=["Y:string"],
                signature="x -> y",
                category="planner",
                deterministic_only=True,
            )

    def test_unknown_input_type_raises(self):
        with pytest.raises(ValueError, match="Unknown input type"):
            chirp_create(
                pins_in=["X:FooBar"],
                pins_out=["Y:int"],
                signature="x -> y",
                category="planner",
            )

    def test_geometry_output_is_string_field(self):
        """Geometry output types must be C# string fields (LLM returns text)."""
        result = chirp_create(
            pins_in=["Desc:string"],
            pins_out=["Center:Point3d"],
            signature="desc -> center",
            category="planner",
        )
        script = result["script"]
        assert "ReadString(" in script

    def test_signature_with_quotes_escaped(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["Y:int"],
            signature='given a "description" -> y',
            category="planner",
        )
        assert 'description' in result["script"]

    def test_pin_metadata(self):
        result = chirp_create(
            pins_in=["Surface:Surface", "Intent:string"],
            pins_out=["UCount:int"],
            signature="surface, intent -> u_count",
            category="planner",
        )
        assert result["pins_in"][0] == {"name": "Surface", "type": "Surface"}
        assert result["pins_in"][1] == {"name": "Intent", "type": "string"}
        assert result["pins_out"][0] == {"name": "UCount", "type": "int"}

    def test_model_override_in_script(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["Y:int"],
            signature="x -> y",
            category="classifier",
            model="openai/mercury-2",
        )
        assert '"model"' in result["script"]
        assert "mercury-2" in result["script"]
        assert result["model"] == "openai/mercury-2"

    def test_no_model_omits_field(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["Y:int"],
            signature="x -> y",
            category="planner",
        )
        assert 'BuildRequestJson(@"x -> y", @"planner", null, inputs, schema)' in result["script"]
        assert result["model"] is None

    def test_category_in_result(self):
        result = chirp_create(
            pins_in=["X:string"],
            pins_out=["Y:int"],
            signature="x -> y",
            category="critic",
        )
        assert result["category"] == "critic"
        assert result["category_info"]["module"] == "ChainOfThought"
