# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

__all__ = [
    "OAuthTokenCache",
    "UsernamePasswordAuthenticator",
    "OAuthAuthenticator",
    "CustomHeaderAuthenticator",
    "AuthenticationManager",
]

import os
import time
import logging
import httpx
from typing import Optional, Dict

try:
    from .exceptions import AuthenticationError
except ImportError:
    from exceptions import AuthenticationError


class OAuthTokenCache:
    """Manages OAuth token caching with automatic expiration."""

    def __init__(self):
        self._token: Optional[str] = None
        self._expiry: float = 0

    def get_token(self) -> Optional[str]:
        """Get cached token if still valid."""
        if self._token and time.time() < self._expiry:
            return self._token
        return None

    def set_token(self, token: str, expires_in: int = 3600) -> None:
        """Cache token with expiration time."""
        self._token = token
        self._expiry = time.time() + expires_in

    def clear_token(self) -> None:
        """Clear cached token."""
        self._token = None
        self._expiry = 0


class UsernamePasswordAuthenticator:
    """Handles username/password authentication for API requests."""

    def __init__(self, username: str, password: str, login_endpoint: str = None):
        self._cache = OAuthTokenCache()  # Reuse the token cache
        self._username = username
        self._password = password
        self._login_endpoint = login_endpoint

    def get_access_token(self) -> Optional[str]:
        """Get valid access token, refreshing if necessary."""
        # Try cached token first
        token = self._cache.get_token()
        if token:
            return token

        if not self._login_endpoint:
            logging.info("No login endpoint configured; cannot authenticate")
            return None

        return self._fetch_new_token()

    def _fetch_new_token(self) -> str:
        """Fetch new token using username/password."""
        try:
            # Try form data first (common for OAuth2-style endpoints)
            response = httpx.post(
                self._login_endpoint,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "password", "username": self._username, "password": self._password, "scope": ""},
            )

            if response.status_code == 422:
                # If form data fails, try JSON
                response = httpx.post(
                    self._login_endpoint,
                    headers={"Content-Type": "application/json"},
                    json={"username": self._username, "password": self._password},
                )

            response.raise_for_status()

            token_data = response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise AuthenticationError("No access_token in login response")

            expires_in = token_data.get("expires_in", 3600)
            self._cache.set_token(access_token, expires_in)

            logging.info("Login successful, token obtained")
            return access_token

        except httpx.HTTPStatusError as e:
            raise AuthenticationError(f"Login failed: {e.response.status_code} {e.response.text}")
        except Exception as e:
            raise AuthenticationError(f"Failed to authenticate: {e}")

    def add_auth_headers(self, headers: dict) -> dict:
        """Add authentication headers to request."""
        token = self.get_access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def is_configured(self) -> bool:
        """Check if username/password auth is properly configured."""
        return bool(self._username and self._password and self._login_endpoint)


class OAuthAuthenticator:
    """Handles OAuth authentication for API requests."""

    def __init__(self):
        self._cache = OAuthTokenCache()
        self._client_id = os.environ.get("OAUTH_CLIENT_ID")
        self._client_secret = os.environ.get("OAUTH_CLIENT_SECRET")
        self._token_url = os.environ.get("OAUTH_TOKEN_URL")
        self._scope = os.environ.get("OAUTH_SCOPE", "api")

    def get_access_token(self) -> Optional[str]:
        """Get valid access token, refreshing if necessary."""
        # Try cached token first
        token = self._cache.get_token()
        if token:
            return token

        # If no OAuth credentials, return None (API may work without auth)
        if not all([self._client_id, self._client_secret, self._token_url]):
            logging.info("No OAuth credentials provided; proceeding without authentication")
            return None

        return self._fetch_new_token()

    def _fetch_new_token(self) -> str:
        """Fetch new token from OAuth server."""
        try:
            response = httpx.post(
                self._token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "scope": self._scope,
                },
            )
            response.raise_for_status()

            token_data = response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise AuthenticationError("No access_token in OAuth response")

            expires_in = token_data.get("expires_in", 3600)
            self._cache.set_token(access_token, expires_in)

            logging.info("OAuth token obtained successfully")
            return access_token

        except httpx.HTTPStatusError as e:
            raise AuthenticationError(f"OAuth token request failed: {e.response.status_code} {e.response.text}")
        except Exception as e:
            raise AuthenticationError(f"Failed to obtain OAuth token: {e}")

    def add_auth_headers(self, headers: dict) -> dict:
        """Add authentication headers to request."""
        token = self.get_access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def is_configured(self) -> bool:
        """Check if OAuth is properly configured."""
        return all([self._client_id, self._client_secret, self._token_url])


class CustomHeaderAuthenticator:
    """Handles custom header authentication for API requests."""

    def __init__(self, headers: Dict[str, str]):
        """Initialize with custom headers.

        Args:
            headers: Dictionary of custom authentication headers
        """
        self._headers = headers.copy() if headers else {}
        if self._headers:
            # Don't log header values for security
            logging.info(f"Custom header authentication configured with {len(self._headers)} headers")

    def add_auth_headers(self, headers: dict) -> dict:
        """Add custom authentication headers to request.

        Args:
            headers: Existing request headers

        Returns:
            Updated headers dictionary
        """
        headers.update(self._headers)
        return headers

    def is_configured(self) -> bool:
        """Check if custom headers are configured."""
        return bool(self._headers)

    def get_headers(self) -> Dict[str, str]:
        """Get a copy of the custom headers."""
        return self._headers.copy()


class AuthenticationManager:
    """Manages different authentication methods."""

    def __init__(self, config):
        self._config = config
        self._oauth_auth = None
        self._username_auth = None
        self._custom_auth = None

        # Initialize custom header authenticator if configured
        if config.has_custom_headers():
            self._custom_auth = CustomHeaderAuthenticator(config.auth_headers)

        # Initialize OAuth authenticator if configured
        if config.is_oauth_configured():
            self._oauth_auth = OAuthAuthenticator()
            logging.info("OAuth authentication configured")

        # Initialize username/password authenticator if configured
        if config.is_username_auth_configured():
            login_endpoint = config.login_endpoint
            if not login_endpoint:
                # Try to auto-detect login endpoint from common patterns
                base_url = config.openapi_url.rsplit("/", 1)[0]
                login_endpoint = f"{base_url}/auth/token"
                logging.info(f"Auto-detected login endpoint: {login_endpoint}")

            self._username_auth = UsernamePasswordAuthenticator(config.username, config.password, login_endpoint)
            logging.info("Username/password authentication configured")

    def get_access_token(self) -> Optional[str]:
        """Get access token using the configured authentication method."""
        # Try username/password auth first if configured
        if self._username_auth and self._username_auth.is_configured():
            try:
                return self._username_auth.get_access_token()
            except AuthenticationError as e:
                logging.warning(f"Username/password authentication failed: {e}")

        # Fall back to OAuth if configured
        if self._oauth_auth and self._oauth_auth.is_configured():
            try:
                return self._oauth_auth.get_access_token()
            except AuthenticationError as e:
                logging.warning(f"OAuth authentication failed: {e}")

        logging.info("No authentication configured or all methods failed")
        return None

    def add_auth_headers(self, headers: dict) -> dict:
        """Add authentication headers to request.

        Applies headers in the following order:
        1. Custom headers (API keys, etc.)
        2. OAuth/Username token (if available)

        Args:
            headers: Existing request headers

        Returns:
            Updated headers dictionary
        """
        # Apply custom headers first
        if self._custom_auth and self._custom_auth.is_configured():
            headers = self._custom_auth.add_auth_headers(headers)

        # Then add token-based auth if available (may override Authorization header)
        token = self.get_access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def get_custom_headers(self) -> Dict[str, str]:
        """Get custom authentication headers if configured.

        Returns:
            Dictionary of custom headers or empty dict
        """
        if self._custom_auth:
            return self._custom_auth.get_headers()
        return {}

    def is_configured(self) -> bool:
        """Check if any authentication method is configured."""
        return (
            (self._custom_auth and self._custom_auth.is_configured())
            or (self._oauth_auth and self._oauth_auth.is_configured())
            or (self._username_auth and self._username_auth.is_configured())
        )
