# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

"""Tests for schema_converter module."""

import pytest
from openapi_mcp.schema_converter import SchemaConverter, NameSanitizer, ResourceNameProcessor


class TestSchemaConverter:
    """Tests for SchemaConverter class."""

    def test_convert_empty_schema(self):
        """Test converting empty/None schema."""
        result = SchemaConverter.convert_openapi_to_mcp_schema(None)
        assert result == {"type": "object", "properties": {}}

        result = SchemaConverter.convert_openapi_to_mcp_schema({})
        assert result == {"type": "object", "properties": {}}

    def test_convert_simple_schema(self):
        """Test converting simple schema with basic types."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "User name"},
                "age": {"type": "integer", "description": "User age"},
            },
            "required": ["name"],
        }
        result = SchemaConverter.convert_openapi_to_mcp_schema(schema)

        assert result["type"] == "object"
        assert "name" in result["properties"]
        assert "age" in result["properties"]
        assert result["properties"]["name"]["type"] == "string"
        assert result["properties"]["age"]["type"] == "number"  # integer -> number
        assert result["required"] == ["name"]

    def test_convert_integer_to_number(self):
        """Test that integer type is converted to number."""
        schema = {
            "properties": {
                "count": {"type": "integer", "description": "Count"},
            },
        }
        result = SchemaConverter.convert_openapi_to_mcp_schema(schema)
        assert result["properties"]["count"]["type"] == "number"

    def test_convert_nested_object(self):
        """Test converting nested object schema."""
        schema = {
            "properties": {
                "address": {
                    "type": "object",
                    "description": "User address",
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                    },
                },
            },
        }
        result = SchemaConverter.convert_openapi_to_mcp_schema(schema)

        assert result["properties"]["address"]["type"] == "object"
        assert "street" in result["properties"]["address"]["properties"]
        assert "city" in result["properties"]["address"]["properties"]

    def test_convert_array_schema(self):
        """Test converting array schema."""
        schema = {
            "properties": {
                "tags": {
                    "type": "array",
                    "description": "User tags",
                    "items": {"type": "string"},
                },
            },
        }
        result = SchemaConverter.convert_openapi_to_mcp_schema(schema)

        assert result["properties"]["tags"]["type"] == "array"
        assert "items" in result["properties"]["tags"]

    def test_convert_non_dict_schema(self):
        """Test converting non-dict schema returns default."""
        result = SchemaConverter._convert_schema_recursive("not a dict")
        assert result == {"type": "string", "description": ""}

    def test_convert_non_dict_property(self):
        """Test converting non-dict property returns default."""
        result = SchemaConverter._convert_property("not a dict")
        assert result == {"type": "string", "description": ""}


class TestNameSanitizer:
    """Tests for NameSanitizer class."""

    def test_sanitize_simple_name(self):
        """Test sanitizing simple name."""
        assert NameSanitizer.sanitize_name("hello_world") == "hello_world"
        assert NameSanitizer.sanitize_name("HelloWorld") == "HelloWorld"
        assert NameSanitizer.sanitize_name("test-name") == "test-name"

    def test_sanitize_special_characters(self):
        """Test sanitizing names with special characters."""
        assert NameSanitizer.sanitize_name("hello world") == "hello_world"
        assert NameSanitizer.sanitize_name("hello@world") == "hello_world"
        assert NameSanitizer.sanitize_name("hello.world") == "hello_world"

    def test_sanitize_name_starting_with_number(self):
        """Test sanitizing names starting with numbers."""
        assert NameSanitizer.sanitize_name("123abc") == "_123abc"
        assert NameSanitizer.sanitize_name("0test") == "_0test"

    def test_sanitize_name_max_length(self):
        """Test truncating long names."""
        long_name = "a" * 100
        result = NameSanitizer.sanitize_name(long_name)
        assert len(result) == 64

        result_custom = NameSanitizer.sanitize_name(long_name, max_length=32)
        assert len(result_custom) == 32

    def test_sanitize_tool_name_with_prefix(self):
        """Test sanitizing tool name with server prefix."""
        result = NameSanitizer.sanitize_tool_name("get_users", "api")
        assert result == "api_get_users"

    def test_sanitize_tool_name_without_prefix(self):
        """Test sanitizing tool name without prefix."""
        result = NameSanitizer.sanitize_tool_name("get_users")
        assert result == "get_users"

    def test_sanitize_resource_name_with_prefix(self):
        """Test sanitizing resource name with prefix."""
        result = NameSanitizer.sanitize_resource_name("User", "api")
        assert result == "api_User"


class TestResourceNameProcessor:
    """Tests for ResourceNameProcessor class."""

    def test_singularize_regular_plural(self):
        """Test singularizing regular plural."""
        assert ResourceNameProcessor.singularize_resource("users") == "user"
        assert ResourceNameProcessor.singularize_resource("items") == "item"
        assert ResourceNameProcessor.singularize_resource("products") == "product"

    def test_singularize_ies_plural(self):
        """Test singularizing words ending in -ies."""
        assert ResourceNameProcessor.singularize_resource("categories") == "category"
        assert ResourceNameProcessor.singularize_resource("stories") == "story"

    def test_singularize_keeps_sses(self):
        """Test words ending in -sses are kept as-is."""
        assert ResourceNameProcessor.singularize_resource("classes") == "classes"

    def test_singularize_already_singular(self):
        """Test already singular words are unchanged."""
        assert ResourceNameProcessor.singularize_resource("user") == "user"
        assert ResourceNameProcessor.singularize_resource("class") == "class"

    def test_singularize_keeps_ss_ending(self):
        """Test words ending in -ss are kept as-is."""
        assert ResourceNameProcessor.singularize_resource("boss") == "boss"
        assert ResourceNameProcessor.singularize_resource("address") == "address"
