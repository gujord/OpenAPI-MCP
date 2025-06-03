# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

import os
import sys
from typing import Optional
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
        
        self._validate_config()
    
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