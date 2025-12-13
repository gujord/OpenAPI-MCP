# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

__all__ = ["ServerConfig"]

import os
import sys
import json
import logging
from typing import Optional, Dict
try:
    from .exceptions import ConfigurationError
except ImportError:
    from exceptions import ConfigurationError


class ServerConfig:
    """Configuration management for MCP server."""
    
    def __init__(self):
        self._openapi_url = os.environ.get("OPENAPI_URL")
        self._server_name = os.environ.get("SERVER_NAME", "openapi_proxy_server")
        self._oauth_client_id = os.environ.get("OAUTH_CLIENT_ID")
        self._oauth_client_secret = os.environ.get("OAUTH_CLIENT_SECRET")
        self._oauth_token_url = os.environ.get("OAUTH_TOKEN_URL")
        self._oauth_scope = os.environ.get("OAUTH_SCOPE", "api")
        
        # Username/password authentication
        self._username = os.environ.get("API_USERNAME")
        self._password = os.environ.get("API_PASSWORD")
        self._login_endpoint = os.environ.get("API_LOGIN_ENDPOINT")
        
        # SSE configuration (deprecated - use MCP_HTTP_ENABLED)
        self._sse_enabled = os.environ.get("SSE_ENABLED", "false").lower() == "true"
        self._sse_host = os.environ.get("SSE_HOST", "127.0.0.1")
        self._sse_port = int(os.environ.get("SSE_PORT", "8000"))
        
        # MCP HTTP Transport configuration
        self._mcp_http_enabled = os.environ.get("MCP_HTTP_ENABLED", "false").lower() == "true"
        self._mcp_http_host = os.environ.get("MCP_HTTP_HOST", "127.0.0.1")
        self._mcp_http_port = int(os.environ.get("MCP_HTTP_PORT", "8000"))
        self._mcp_cors_origins = os.environ.get("MCP_CORS_ORIGINS", "*").split(",")
        self._mcp_message_size_limit = os.environ.get("MCP_MESSAGE_SIZE_LIMIT", "4mb")
        self._mcp_batch_timeout = int(os.environ.get("MCP_BATCH_TIMEOUT", "30"))
        self._mcp_session_timeout = int(os.environ.get("MCP_SESSION_TIMEOUT", "3600"))
        
        # Custom authentication headers
        self._auth_headers_raw = os.environ.get("MCP_AUTH_HEADERS", "")
        self._auth_headers = self._parse_auth_headers()
        
        self._validate_config()
    
    def _parse_auth_headers(self) -> Dict[str, str]:
        """Parse custom authentication headers from environment variable.
        
        Supports two formats:
        1. JSON: {"X-API-Key": "secret", "X-Client-ID": "123"}
        2. Simple: X-API-Key=secret,X-Client-ID=123
        
        Returns:
            Dictionary of parsed headers
        """
        if not self._auth_headers_raw:
            return {}
        
        try:
            # Try parsing as JSON first
            headers = json.loads(self._auth_headers_raw)
            if not isinstance(headers, dict):
                raise ValueError("MCP_AUTH_HEADERS must be a JSON object")
            # Ensure all values are strings
            return {k: str(v) for k, v in headers.items()}
        except json.JSONDecodeError:
            # Fall back to simple format: key=value,key2=value2
            headers = {}
            for pair in self._auth_headers_raw.split(','):
                pair = pair.strip()
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    headers[key.strip()] = value.strip()
            
            if headers:
                logging.info(f"Parsed {len(headers)} custom authentication headers")
            
            return headers
    
    def _validate_config(self):
        """Validate required configuration."""
        if not self._openapi_url:
            raise ConfigurationError("OPENAPI_URL environment variable is required")
    
    @property
    def openapi_url(self) -> str:
        """Get OpenAPI spec URL."""
        return self._openapi_url
    
    @property
    def server_name(self) -> str:
        """Get server name."""
        return self._server_name
    
    @property
    def oauth_client_id(self) -> Optional[str]:
        """Get OAuth client ID."""
        return self._oauth_client_id
    
    @property
    def oauth_client_secret(self) -> Optional[str]:
        """Get OAuth client secret."""
        return self._oauth_client_secret
    
    @property
    def oauth_token_url(self) -> Optional[str]:
        """Get OAuth token URL."""
        return self._oauth_token_url
    
    @property
    def oauth_scope(self) -> str:
        """Get OAuth scope."""
        return self._oauth_scope
    
    def is_oauth_configured(self) -> bool:
        """Check if OAuth is properly configured."""
        return all([
            self._oauth_client_id,
            self._oauth_client_secret,
            self._oauth_token_url
        ])
    
    @property
    def username(self) -> Optional[str]:
        """Get API username."""
        return self._username
    
    @property
    def password(self) -> Optional[str]:
        """Get API password."""
        return self._password
    
    @property
    def login_endpoint(self) -> Optional[str]:
        """Get API login endpoint."""
        return self._login_endpoint
    
    def is_username_auth_configured(self) -> bool:
        """Check if username/password authentication is configured."""
        return bool(self._username and self._password)
    
    def get_oauth_config(self) -> dict:
        """Get OAuth configuration as dictionary."""
        return {
            "client_id": self._oauth_client_id,
            "client_secret": self._oauth_client_secret,
            "token_url": self._oauth_token_url,
            "scope": self._oauth_scope
        }
    
    def get_username_auth_config(self) -> dict:
        """Get username/password authentication configuration."""
        return {
            "username": self._username,
            "password": self._password,
            "login_endpoint": self._login_endpoint
        }
    
    @property
    def sse_enabled(self) -> bool:
        """Check if SSE is enabled."""
        return self._sse_enabled
    
    @property
    def sse_host(self) -> str:
        """Get SSE server host."""
        return self._sse_host
    
    @property
    def sse_port(self) -> int:
        """Get SSE server port."""
        return self._sse_port
    
    def get_sse_config(self) -> dict:
        """Get SSE configuration."""
        return {
            "enabled": self._sse_enabled,
            "host": self._sse_host,
            "port": self._sse_port
        }
    
    @property
    def mcp_http_enabled(self) -> bool:
        """Check if MCP HTTP transport is enabled."""
        return self._mcp_http_enabled
    
    @property
    def mcp_http_host(self) -> str:
        """Get MCP HTTP transport host."""
        return self._mcp_http_host
    
    @property
    def mcp_http_port(self) -> int:
        """Get MCP HTTP transport port."""
        return self._mcp_http_port
    
    @property
    def mcp_cors_origins(self) -> list:
        """Get CORS origins for MCP HTTP transport."""
        return self._mcp_cors_origins
    
    @property
    def mcp_message_size_limit(self) -> str:
        """Get message size limit for MCP HTTP transport."""
        return self._mcp_message_size_limit
    
    @property
    def mcp_batch_timeout(self) -> int:
        """Get batch timeout for MCP HTTP transport."""
        return self._mcp_batch_timeout
    
    @property
    def mcp_session_timeout(self) -> int:
        """Get session timeout for MCP HTTP transport."""
        return self._mcp_session_timeout
    
    def get_mcp_http_config(self) -> dict:
        """Get MCP HTTP transport configuration."""
        return {
            "enabled": self._mcp_http_enabled,
            "host": self._mcp_http_host,
            "port": self._mcp_http_port,
            "cors_origins": self._mcp_cors_origins,
            "message_size_limit": self._mcp_message_size_limit,
            "batch_timeout": self._mcp_batch_timeout,
            "session_timeout": self._mcp_session_timeout
        }
    
    @property
    def auth_headers(self) -> Dict[str, str]:
        """Get custom authentication headers."""
        return self._auth_headers.copy()
    
    def has_custom_headers(self) -> bool:
        """Check if custom authentication headers are configured."""
        return bool(self._auth_headers)