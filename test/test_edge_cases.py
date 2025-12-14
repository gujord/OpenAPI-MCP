# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

"""Parametrized tests for edge cases."""

import os
import json
import tempfile
import pytest
import yaml
from pathlib import Path

from openapi_mcp.request_handler import PathSanitizer, KwargsParser
from openapi_mcp.config import ServerConfig, load_config_from_file
from openapi_mcp.exceptions import ConfigurationError, ParameterError
from openapi_mcp.schema_converter import NameSanitizer


class TestPathSanitizerEdgeCases:
    """Parametrized tests for path sanitizer edge cases."""

    @pytest.mark.parametrize(
        "value,param_name,expected",
        [
            ("simple", "id", "simple"),
            ("123", "id", "123"),
            ("user-name", "id", "user-name"),
            ("user_name", "id", "user_name"),
            ("user.name", "id", "user.name"),
            ("UPPERCASE", "id", "UPPERCASE"),
            ("MixedCase123", "id", "MixedCase123"),
        ],
    )
    def test_valid_path_parameters(self, value, param_name, expected):
        """Test valid path parameter values."""
        result = PathSanitizer.sanitize_path_parameter(value, param_name)
        assert result == expected

    @pytest.mark.parametrize(
        "value,param_name",
        [
            ("../etc/passwd", "id"),
            ("..\\windows\\system32", "id"),
            ("foo/../bar", "path"),
            ("foo/..\\bar", "path"),
            ("../../secret", "file"),
        ],
    )
    def test_path_traversal_attacks_blocked(self, value, param_name):
        """Test that path traversal attempts are blocked."""
        with pytest.raises(ParameterError) as exc_info:
            PathSanitizer.sanitize_path_parameter(value, param_name)
        assert "invalid sequence '..'" in str(exc_info.value)

    @pytest.mark.parametrize(
        "value,param_name",
        [
            ("foo/bar", "id"),
            ("foo\\bar", "id"),
            ("/absolute/path", "file"),
            ("C:\\windows\\path", "path"),
        ],
    )
    def test_path_separators_blocked(self, value, param_name):
        """Test that path separators are blocked."""
        with pytest.raises(ParameterError) as exc_info:
            PathSanitizer.sanitize_path_parameter(value, param_name)
        assert "invalid path separator" in str(exc_info.value)

    @pytest.mark.parametrize(
        "value,param_name",
        [
            ("foo\x00bar", "id"),
            ("\x00", "id"),
            ("test\x00.txt", "file"),
        ],
    )
    def test_null_bytes_blocked(self, value, param_name):
        """Test that null bytes are blocked."""
        with pytest.raises(ParameterError) as exc_info:
            PathSanitizer.sanitize_path_parameter(value, param_name)
        assert "null byte" in str(exc_info.value)

    @pytest.mark.parametrize(
        "value,param_name",
        [
            ("", "id"),
        ],
    )
    def test_empty_values_blocked(self, value, param_name):
        """Test that empty values are blocked."""
        with pytest.raises(ParameterError) as exc_info:
            PathSanitizer.sanitize_path_parameter(value, param_name)
        assert "cannot be empty" in str(exc_info.value)


class TestKwargsParserEdgeCases:
    """Parametrized tests for kwargs parser edge cases."""

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            # Standard JSON
            ('{"key": "value"}', {"key": "value"}),
            ('{"a": 1, "b": 2}', {"a": 1, "b": 2}),
            # Numeric values
            ('{"lat": 63.1115}', {"lat": 63.1115}),
            ('{"count": 42}', {"count": 42}),
            # Query string format
            ("key=value&key2=value2", {"key": "value", "key2": "value2"}),
            # Comma-separated format (query string style with &)
            ("lat=63.1115&lon=7.7327", {"lat": "63.1115", "lon": "7.7327"}),
        ],
    )
    def test_parse_various_formats(self, input_str, expected):
        """Test parsing various input formats."""
        result = KwargsParser.parse_kwargs_string(input_str)
        assert result == expected

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            # With backticks
            ("`key=value`", {"key": "value"}),
            ("```key=value```", {"key": "value"}),
            # With question mark prefix
            ("?key=value", {"key": "value"}),
            # With whitespace
            ("  key=value  ", {"key": "value"}),
        ],
    )
    def test_parse_with_formatting(self, input_str, expected):
        """Test parsing with various formatting artifacts."""
        result = KwargsParser.parse_kwargs_string(input_str)
        assert result == expected

    @pytest.mark.parametrize(
        "input_str",
        [
            "invalid",
            "no_equals",
            "",
            "   ",
        ],
    )
    def test_unparseable_returns_empty(self, input_str):
        """Test that unparseable strings return empty dict."""
        result = KwargsParser.parse_kwargs_string(input_str)
        assert result == {}


class TestConfigFileEdgeCases:
    """Parametrized tests for config file loading edge cases."""

    @pytest.mark.parametrize(
        "content,file_ext,expected_url",
        [
            # YAML format
            ("openapi_url: https://api.example.com/spec.json", ".yaml", "https://api.example.com/spec.json"),
            ("openapi_url: https://api.example.com/spec.json", ".yml", "https://api.example.com/spec.json"),
            # JSON format
            ('{"openapi_url": "https://api.example.com/spec.json"}', ".json", "https://api.example.com/spec.json"),
        ],
    )
    def test_load_config_from_file_formats(self, content, file_ext, expected_url):
        """Test loading config from different file formats."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=file_ext, delete=False) as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            result = load_config_from_file(temp_path)
            assert result.get("openapi_url") == expected_url
        finally:
            os.unlink(temp_path)

    @pytest.mark.parametrize(
        "file_ext,content",
        [
            (".yaml", "invalid: yaml: content: ["),
            (".json", "{invalid json}"),
        ],
    )
    def test_invalid_config_file_content(self, file_ext, content):
        """Test error handling for invalid file content."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=file_ext, delete=False) as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError):
                load_config_from_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_unsupported_file_format(self):
        """Test error for unsupported file format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("openapi_url: test")
            f.flush()
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError) as exc_info:
                load_config_from_file(temp_path)
            assert "Unsupported config file format" in str(exc_info.value)
        finally:
            os.unlink(temp_path)

    def test_missing_config_file(self):
        """Test error for missing config file."""
        with pytest.raises(ConfigurationError) as exc_info:
            load_config_from_file("/nonexistent/path/config.yaml")
        assert "Configuration file not found" in str(exc_info.value)


class TestNameSanitizerEdgeCases:
    """Parametrized tests for name sanitizer edge cases."""

    @pytest.mark.parametrize(
        "input_name,expected",
        [
            # Special characters
            ("hello world", "hello_world"),
            ("hello@world#test", "hello_world_test"),
            ("foo.bar.baz", "foo_bar_baz"),
            ("test(123)", "test_123_"),
            # Unicode
            ("café", "caf_"),
            ("日本語", "___"),
            # Empty sections
            ("a__b", "a__b"),
            ("---", "---"),
        ],
    )
    def test_sanitize_special_names(self, input_name, expected):
        """Test sanitizing names with various special characters."""
        result = NameSanitizer.sanitize_name(input_name)
        assert result == expected

    @pytest.mark.parametrize(
        "input_name,max_len,expected_len",
        [
            ("a" * 100, 64, 64),
            ("a" * 100, 32, 32),
            ("a" * 100, 10, 10),
            ("short", 64, 5),
        ],
    )
    def test_max_length_truncation(self, input_name, max_len, expected_len):
        """Test max length truncation."""
        result = NameSanitizer.sanitize_name(input_name, max_length=max_len)
        assert len(result) == expected_len

    @pytest.mark.parametrize(
        "input_name,expected_prefix",
        [
            ("0test", "_0"),
            ("123abc", "_123"),
            ("9", "_9"),
        ],
    )
    def test_numeric_prefix_handling(self, input_name, expected_prefix):
        """Test handling of names starting with numbers."""
        result = NameSanitizer.sanitize_name(input_name)
        assert result.startswith(expected_prefix)


class TestServerConfigEdgeCases:
    """Parametrized tests for ServerConfig edge cases."""

    @pytest.mark.parametrize(
        "env_vars,expected_oauth",
        [
            # Complete OAuth config
            (
                {
                    "OPENAPI_URL": "https://api.example.com/spec.json",
                    "OAUTH_CLIENT_ID": "client123",
                    "OAUTH_CLIENT_SECRET": "secret456",
                    "OAUTH_TOKEN_URL": "https://auth.example.com/token",
                },
                True,
            ),
            # Missing client secret
            (
                {
                    "OPENAPI_URL": "https://api.example.com/spec.json",
                    "OAUTH_CLIENT_ID": "client123",
                    "OAUTH_TOKEN_URL": "https://auth.example.com/token",
                },
                False,
            ),
            # No OAuth config
            (
                {"OPENAPI_URL": "https://api.example.com/spec.json"},
                False,
            ),
        ],
    )
    def test_oauth_configuration_detection(self, env_vars, expected_oauth):
        """Test OAuth configuration detection."""
        # Save original env
        original_env = {k: os.environ.get(k) for k in env_vars}

        try:
            # Set test env vars
            for key, value in env_vars.items():
                os.environ[key] = value

            config = ServerConfig()
            assert config.is_oauth_configured() == expected_oauth
        finally:
            # Restore original env
            for key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value

    @pytest.mark.parametrize(
        "auth_headers_raw,expected_headers",
        [
            # JSON format
            ('{"X-API-Key": "test123"}', {"X-API-Key": "test123"}),
            ('{"Authorization": "Bearer token"}', {"Authorization": "Bearer token"}),
            # Key=value format
            ("X-API-Key=test123", {"X-API-Key": "test123"}),
            ("X-API-Key=test123,X-Custom=value", {"X-API-Key": "test123", "X-Custom": "value"}),
            # Empty
            ("", {}),
        ],
    )
    def test_auth_headers_parsing(self, auth_headers_raw, expected_headers):
        """Test custom auth headers parsing."""
        # Save original env
        original_url = os.environ.get("OPENAPI_URL")
        original_headers = os.environ.get("MCP_AUTH_HEADERS")

        try:
            os.environ["OPENAPI_URL"] = "https://api.example.com/spec.json"
            os.environ["MCP_AUTH_HEADERS"] = auth_headers_raw

            config = ServerConfig()
            assert config.auth_headers == expected_headers
        finally:
            # Restore original env
            if original_url is None:
                os.environ.pop("OPENAPI_URL", None)
            else:
                os.environ["OPENAPI_URL"] = original_url
            if original_headers is None:
                os.environ.pop("MCP_AUTH_HEADERS", None)
            else:
                os.environ["MCP_AUTH_HEADERS"] = original_headers
