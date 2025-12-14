# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

__all__ = ["OpenAPILoader", "OpenAPIParser"]

import json
import logging
import yaml
import httpx
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, Any, Tuple, List, Optional

try:
    from .exceptions import OpenAPIError
except ImportError:
    from exceptions import OpenAPIError


class OpenAPILoader:
    """Handles loading and parsing of OpenAPI specifications."""

    @staticmethod
    def load_spec(openapi_url: str, auth_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Load OpenAPI spec from URL or local file.

        Args:
            openapi_url: URL or file path to OpenAPI specification
            auth_headers: Optional custom headers for HTTP requests

        Returns:
            Parsed OpenAPI specification dictionary

        Raises:
            OpenAPIError: If spec cannot be loaded or is invalid
        """
        try:
            # Check if it's a local file or remote URL
            if not openapi_url.startswith(("http://", "https://")):
                return OpenAPILoader._load_local_file(openapi_url)
            else:
                return OpenAPILoader._load_remote_url(openapi_url, auth_headers)
        except (OpenAPIError, FileNotFoundError):
            raise  # Re-raise these exceptions as-is
        except (httpx.RequestError, json.JSONDecodeError, yaml.YAMLError) as e:
            raise OpenAPIError(f"Failed to load OpenAPI spec: {e}")

    @staticmethod
    def _load_local_file(file_path: str) -> Dict[str, Any]:
        """Load OpenAPI spec from local file.

        Args:
            file_path: Path to local OpenAPI spec file

        Returns:
            Parsed OpenAPI specification dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            OpenAPIError: If file cannot be parsed or is invalid
        """
        try:
            # Resolve path (handles relative and absolute paths)
            path = Path(file_path).resolve()

            if not path.exists():
                raise FileNotFoundError(f"OpenAPI spec file not found: {file_path}")

            if not path.is_file():
                raise OpenAPIError(f"Path is not a file: {file_path}")

            # Check file size limit (10MB)
            if path.stat().st_size > 10 * 1024 * 1024:
                raise OpenAPIError(f"OpenAPI spec file too large (>10MB): {file_path}")

            with open(path, "r", encoding="utf-8") as f:
                # Detect format by extension
                if path.suffix.lower() in [".yml", ".yaml"]:
                    spec = yaml.safe_load(f)
                else:
                    # Default to JSON for .json or unknown extensions
                    spec = json.load(f)

            logging.info(f"Loaded local OpenAPI spec from: {path}")

        except FileNotFoundError:
            raise  # Re-raise FileNotFoundError as-is
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            raise OpenAPIError(f"Failed to parse OpenAPI spec file: {e}")
        except (IOError, OSError) as e:
            raise OpenAPIError(f"Failed to read OpenAPI spec file: {e}")

        # Validate spec structure
        if not isinstance(spec, dict) or "paths" not in spec or "info" not in spec:
            raise OpenAPIError("Invalid OpenAPI spec: Missing required properties 'paths' or 'info'")

        return spec

    @staticmethod
    def _load_remote_url(url: str, auth_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Load OpenAPI spec from remote URL.

        Args:
            url: HTTP/HTTPS URL to OpenAPI specification
            auth_headers: Optional custom headers for the request

        Returns:
            Parsed OpenAPI specification dictionary

        Raises:
            OpenAPIError: If spec cannot be fetched or is invalid
        """
        try:
            # Prepare headers
            headers = auth_headers.copy() if auth_headers else {}

            # Make HTTP request
            response = httpx.get(url, headers=headers)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            if content_type.startswith("application/json"):
                spec = response.json()
            else:
                spec = yaml.safe_load(response.text)

            logging.info(f"Loaded remote OpenAPI spec from: {url}")

        except httpx.HTTPStatusError as e:
            raise OpenAPIError(f"Failed to fetch OpenAPI spec: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            raise OpenAPIError(f"Failed to fetch OpenAPI spec: {e}")
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            raise OpenAPIError(f"Failed to parse remote OpenAPI spec: {e}")

        # Validate spec structure
        if not isinstance(spec, dict) or "paths" not in spec or "info" not in spec:
            raise OpenAPIError("Invalid OpenAPI spec: Missing required properties 'paths' or 'info'")

        return spec

    @staticmethod
    def extract_server_url(spec: Dict[str, Any], openapi_url: str) -> str:
        """Extract server URL from OpenAPI spec."""
        servers = spec.get("servers")
        parsed_url = urlparse(openapi_url)

        # Try to get server URL from servers field
        raw_url = ""
        if isinstance(servers, list) and servers:
            raw_url = servers[0].get("url", "")
        elif isinstance(servers, dict):
            raw_url = servers.get("url", "")

        # Fallback to deriving from openapi_url
        if not raw_url:
            base = parsed_url.path.rsplit("/", 1)[0]
            raw_url = f"{parsed_url.scheme}://{parsed_url.netloc}{base}"

        # Normalize server URL
        if raw_url.startswith("/"):
            server_url = f"{parsed_url.scheme}://{parsed_url.netloc}{raw_url}"
        elif not raw_url.startswith(("http://", "https://")):
            server_url = f"https://{raw_url}"
        else:
            server_url = raw_url

        return server_url


class OpenAPIParser:
    """Parses OpenAPI specifications into operation metadata."""

    def __init__(self, sanitizer_func):
        self._sanitize_name = sanitizer_func

    def parse_operations(self, spec: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Parse operations from OpenAPI spec into tool metadata."""
        operations = {}

        for path, path_item in spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if method.lower() not in {"get", "post", "put", "delete", "patch", "head", "options"}:
                    continue

                # Process request body as parameter
                self._process_request_body(operation)

                # Extract response schema
                response_schema = self._extract_response_schema(operation)

                # Generate operation ID
                raw_op_id = (
                    operation.get("operationId")
                    or f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}"
                )
                sanitized_op_id = self._sanitize_name(raw_op_id)

                # Get operation summary/description
                summary = operation.get("description") or operation.get("summary") or sanitized_op_id

                operations[sanitized_op_id] = {
                    "summary": summary,
                    "parameters": operation.get("parameters", []),
                    "path": path,
                    "method": method.upper(),
                    "responseSchema": response_schema,
                    "tags": operation.get("tags", []),
                }

        logging.info("Parsed %d operations from OpenAPI spec", len(operations))
        return operations

    def _process_request_body(self, operation: Dict[str, Any]) -> None:
        """Convert requestBody to parameter for easier handling."""
        if "requestBody" not in operation:
            return

        req_body = operation["requestBody"]
        body_schema = {}

        if "content" in req_body and "application/json" in req_body["content"]:
            body_schema = req_body["content"]["application/json"].get("schema", {})

        # Add body as a parameter
        operation.setdefault("parameters", []).append(
            {
                "name": "body",
                "in": "body",
                "required": req_body.get("required", False),
                "schema": body_schema,
                "description": "Request body",
            }
        )

    def _extract_response_schema(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Extract response schema from 200 response."""
        responses = operation.get("responses", {})
        if "200" not in responses:
            return None

        response_200 = responses["200"]
        content = response_200.get("content", {})

        if "application/json" in content:
            return content["application/json"].get("schema")

        return None

    def extract_api_info(self, spec: Dict[str, Any]) -> Tuple[str, str]:
        """Extract API title and category from spec."""
        info = spec.get("info", {})
        title = info.get("title", "API")
        category = title.split()[0] if title else "API"
        return title, category
