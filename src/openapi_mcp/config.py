# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

"""Configuration management using pydantic-settings for validation."""

__all__ = ["ServerConfig", "load_config_from_file"]

import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

import yaml
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    from .exceptions import ConfigurationError
except ImportError:
    from exceptions import ConfigurationError


def load_config_from_file(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML or JSON file.

    Args:
        config_path: Path to configuration file (.yaml, .yml, or .json)

    Returns:
        Dictionary of configuration values

    Raises:
        ConfigurationError: If file cannot be loaded or parsed
    """
    path = Path(config_path)

    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {config_path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix.lower() in [".yaml", ".yml"]:
                return yaml.safe_load(f) or {}
            elif path.suffix.lower() == ".json":
                return json.load(f)
            else:
                raise ConfigurationError(f"Unsupported config file format: {path.suffix}")
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        raise ConfigurationError(f"Failed to parse config file: {e}")
    except IOError as e:
        raise ConfigurationError(f"Failed to read config file: {e}")


# Default CORS origins for security (localhost only)
DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080",
]


class ServerConfig(BaseSettings):
    """Configuration management for MCP server using pydantic-settings.

    Configuration can be loaded from:
    1. Environment variables (e.g., OPENAPI_URL, SERVER_NAME)
    2. .env file in the current directory
    3. YAML/JSON config file (via MCP_CONFIG_FILE env var or from_file() method)

    Example with environment variables:
        >>> os.environ["OPENAPI_URL"] = "https://api.example.com/openapi.json"
        >>> config = ServerConfig()
        >>> config.openapi_url
        'https://api.example.com/openapi.json'

    Example with config file:
        >>> config = ServerConfig.from_file("config.yaml")
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Required configuration
    openapi_url: str = Field(
        ...,
        description="URL or path to OpenAPI specification (required)",
        alias="OPENAPI_URL",
    )

    # Server identification
    server_name: str = Field(
        default="openapi_proxy_server",
        description="Name of the MCP server",
        alias="SERVER_NAME",
    )

    # OAuth configuration
    oauth_client_id: Optional[str] = Field(
        default=None,
        description="OAuth client ID",
        alias="OAUTH_CLIENT_ID",
    )
    oauth_client_secret: Optional[str] = Field(
        default=None,
        description="OAuth client secret",
        alias="OAUTH_CLIENT_SECRET",
    )
    oauth_token_url: Optional[str] = Field(
        default=None,
        description="OAuth token endpoint URL",
        alias="OAUTH_TOKEN_URL",
    )
    oauth_scope: str = Field(
        default="api",
        description="OAuth scope",
        alias="OAUTH_SCOPE",
    )

    # Username/password authentication
    username: Optional[str] = Field(
        default=None,
        description="API username for authentication",
        alias="API_USERNAME",
    )
    password: Optional[str] = Field(
        default=None,
        description="API password for authentication",
        alias="API_PASSWORD",
    )
    login_endpoint: Optional[str] = Field(
        default=None,
        description="API login endpoint",
        alias="API_LOGIN_ENDPOINT",
    )

    # SSE configuration (deprecated)
    sse_enabled: bool = Field(
        default=False,
        description="Enable SSE transport (deprecated, use MCP_HTTP_ENABLED)",
        alias="SSE_ENABLED",
    )
    sse_host: str = Field(
        default="127.0.0.1",
        description="SSE server host",
        alias="SSE_HOST",
    )
    sse_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="SSE server port",
        alias="SSE_PORT",
    )

    # MCP HTTP Transport configuration
    mcp_http_enabled: bool = Field(
        default=False,
        description="Enable MCP HTTP transport",
        alias="MCP_HTTP_ENABLED",
    )
    mcp_http_host: str = Field(
        default="127.0.0.1",
        description="MCP HTTP server host",
        alias="MCP_HTTP_HOST",
    )
    mcp_http_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="MCP HTTP server port",
        alias="MCP_HTTP_PORT",
    )
    mcp_cors_origins: str = Field(
        default=",".join(DEFAULT_CORS_ORIGINS),
        description="Comma-separated CORS origins (use * for all)",
        alias="MCP_CORS_ORIGINS",
    )
    mcp_message_size_limit: str = Field(
        default="4mb",
        description="Maximum message size limit",
        alias="MCP_MESSAGE_SIZE_LIMIT",
    )
    mcp_batch_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Batch request timeout in seconds",
        alias="MCP_BATCH_TIMEOUT",
    )
    mcp_session_timeout: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Session timeout in seconds",
        alias="MCP_SESSION_TIMEOUT",
    )

    # Custom authentication headers
    auth_headers_raw: str = Field(
        default="",
        description="Custom auth headers (JSON or key=value,key2=value2 format)",
        alias="MCP_AUTH_HEADERS",
    )

    # HTTP retry configuration
    http_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of HTTP request retries",
        alias="HTTP_MAX_RETRIES",
    )
    http_retry_base_delay: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Base delay between retries in seconds",
        alias="HTTP_RETRY_BASE_DELAY",
    )
    http_retry_max_delay: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Maximum delay between retries in seconds",
        alias="HTTP_RETRY_MAX_DELAY",
    )
    http_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=300.0,
        description="HTTP request timeout in seconds",
        alias="HTTP_TIMEOUT",
    )

    # Debug mode
    debug: bool = Field(
        default=False,
        description="Enable debug logging",
        alias="MCP_DEBUG",
    )

    # Parsed auth headers (computed field)
    _auth_headers: Dict[str, str] = {}

    @model_validator(mode="after")
    def parse_auth_headers(self) -> "ServerConfig":
        """Parse custom authentication headers after initialization."""
        if not self.auth_headers_raw:
            self._auth_headers = {}
            return self

        try:
            # Try parsing as JSON first
            headers = json.loads(self.auth_headers_raw)
            if not isinstance(headers, dict):
                raise ValueError("MCP_AUTH_HEADERS must be a JSON object")
            self._auth_headers = {k: str(v) for k, v in headers.items()}
        except json.JSONDecodeError:
            # Fall back to simple format: key=value,key2=value2
            headers = {}
            for pair in self.auth_headers_raw.split(","):
                pair = pair.strip()
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    headers[key.strip()] = value.strip()

            if headers:
                logging.info(f"Parsed {len(headers)} custom authentication headers")

            self._auth_headers = headers

        return self

    @field_validator("openapi_url")
    @classmethod
    def validate_openapi_url(cls, v: str) -> str:
        """Validate OpenAPI URL is not empty."""
        if not v or not v.strip():
            raise ConfigurationError("OPENAPI_URL environment variable is required")
        return v.strip()

    def is_oauth_configured(self) -> bool:
        """Check if OAuth is properly configured."""
        return all([self.oauth_client_id, self.oauth_client_secret, self.oauth_token_url])

    def is_username_auth_configured(self) -> bool:
        """Check if username/password authentication is configured."""
        return bool(self.username and self.password)

    def get_oauth_config(self) -> dict:
        """Get OAuth configuration as dictionary."""
        return {
            "client_id": self.oauth_client_id,
            "client_secret": self.oauth_client_secret,
            "token_url": self.oauth_token_url,
            "scope": self.oauth_scope,
        }

    def get_username_auth_config(self) -> dict:
        """Get username/password authentication configuration."""
        return {"username": self.username, "password": self.password, "login_endpoint": self.login_endpoint}

    def get_sse_config(self) -> dict:
        """Get SSE configuration."""
        return {"enabled": self.sse_enabled, "host": self.sse_host, "port": self.sse_port}

    def get_mcp_http_config(self) -> dict:
        """Get MCP HTTP transport configuration."""
        return {
            "enabled": self.mcp_http_enabled,
            "host": self.mcp_http_host,
            "port": self.mcp_http_port,
            "cors_origins": self.mcp_cors_origins.split(","),
            "message_size_limit": self.mcp_message_size_limit,
            "batch_timeout": self.mcp_batch_timeout,
            "session_timeout": self.mcp_session_timeout,
        }

    @property
    def auth_headers(self) -> Dict[str, str]:
        """Get custom authentication headers."""
        return self._auth_headers.copy()

    def has_custom_headers(self) -> bool:
        """Check if custom authentication headers are configured."""
        return bool(self._auth_headers)

    def get_http_retry_config(self) -> dict:
        """Get HTTP retry configuration."""
        return {
            "max_retries": self.http_max_retries,
            "base_delay": self.http_retry_base_delay,
            "max_delay": self.http_retry_max_delay,
            "timeout": self.http_timeout,
        }

    @classmethod
    def from_file(cls, config_path: str) -> "ServerConfig":
        """Load configuration from a YAML or JSON file.

        The file values will be merged with environment variables,
        with environment variables taking precedence.

        Args:
            config_path: Path to configuration file (.yaml, .yml, or .json)

        Returns:
            ServerConfig instance

        Raises:
            ConfigurationError: If file cannot be loaded or parsed

        Example config.yaml:
            openapi_url: "https://api.example.com/openapi.json"
            server_name: "my_api"
            mcp_debug: true
            http_timeout: 60
        """
        file_config = load_config_from_file(config_path)

        # Convert keys to uppercase for env var compatibility
        env_style_config = {}
        for key, value in file_config.items():
            # Handle nested config (e.g., oauth.client_id -> OAUTH_CLIENT_ID)
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    env_key = f"{key}_{sub_key}".upper()
                    env_style_config[env_key] = sub_value
            else:
                env_style_config[key.upper()] = value

        # Set environment variables from file config (env vars take precedence)
        for key, value in env_style_config.items():
            if key not in os.environ and value is not None:
                os.environ[key] = str(value)

        return cls()
