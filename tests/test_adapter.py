"""Tests for the ChirpAdapter — type coercion and caching (no live LLM)."""

import pytest
from chirp.adapter import ChirpAdapter


class TestCoercion:
    """Test the adapter's type coercion without hitting an LLM."""

    def setup_method(self):
        self.adapter = ChirpAdapter()

    def test_int_coercion(self):
        assert self.adapter._coerce("42", "int") == 42
        assert self.adapter._coerce("42.7", "int") == 42
        assert self.adapter._coerce(42, "int") == 42

    def test_float_coercion(self):
        assert self.adapter._coerce("3.14", "float") == 3.14
        assert self.adapter._coerce(3, "float") == 3.0

    def test_bool_coercion(self):
        assert self.adapter._coerce("true", "bool") is True
        assert self.adapter._coerce("false", "bool") is False
        assert self.adapter._coerce("yes", "bool") is True
        assert self.adapter._coerce("0", "bool") is False

    def test_string_coercion(self):
        assert self.adapter._coerce(42, "string") == "42"
        assert self.adapter._coerce("hello", "string") == "hello"

    def test_bool_not_coerced_as_int(self):
        """bool is a subclass of int in Python — ensure True doesn't pass as int."""
        result = self.adapter._coerce(True, "int")
        assert result == 1
        assert type(result) is int  # not bool

    def test_geometry_type_coercion(self):
        assert self.adapter._coerce("a flat surface", "Surface") == "a flat surface"


class TestCacheKey:
    """Test deterministic cache key generation."""

    def setup_method(self):
        self.adapter = ChirpAdapter()

    def test_same_inputs_same_key(self):
        k1 = self.adapter._cache_key("a -> b", {"a": 1}, {"b": "int"})
        k2 = self.adapter._cache_key("a -> b", {"a": 1}, {"b": "int"})
        assert k1 == k2

    def test_different_inputs_different_key(self):
        k1 = self.adapter._cache_key("a -> b", {"a": 1}, {"b": "int"})
        k2 = self.adapter._cache_key("a -> b", {"a": 2}, {"b": "int"})
        assert k1 != k2
