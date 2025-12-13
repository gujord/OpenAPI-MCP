# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

import re
from typing import Dict, Any


class SchemaConverter:
    """Converts OpenAPI schemas to MCP-compatible resource schemas."""
    
    @staticmethod
    def convert_openapi_to_mcp_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert OpenAPI schema to MCP resource schema."""
        if not schema:
            return {"type": "object", "properties": {}}
            
        return SchemaConverter._convert_schema_recursive(schema)
    
    @staticmethod
    def _convert_schema_recursive(schema: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively convert schema properties."""
        if not isinstance(schema, dict):
            return {"type": "string", "description": ""}
            
        properties = {}
        required = schema.get("required", [])
        
        for prop_name, prop_schema in schema.get("properties", {}).items():
            converted_prop = SchemaConverter._convert_property(prop_schema)
            properties[prop_name] = converted_prop
            
        resource_schema = {
            "type": "object",
            "properties": properties
        }
        
        if required:
            resource_schema["required"] = required
            
        return resource_schema
    
    @staticmethod
    def _convert_property(prop_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert individual property schema."""
        if not isinstance(prop_schema, dict):
            return {"type": "string", "description": ""}
            
        prop_type = prop_schema.get("type", "string")
        description = prop_schema.get("description", "")
        
        if prop_type == "integer":
            return {
                "type": "number",
                "description": description
            }
        elif prop_type == "array":
            items_schema = SchemaConverter._convert_schema_recursive(
                prop_schema.get("items", {})
            )
            return {
                "type": "array",
                "items": items_schema,
                "description": description
            }
        elif prop_type == "object":
            nested_schema = SchemaConverter._convert_schema_recursive(prop_schema)
            nested_schema["description"] = description
            return nested_schema
        else:
            return {
                "type": prop_type,
                "description": description
            }


class NameSanitizer:
    """Handles name sanitization for tools and resources."""
    
    @staticmethod
    def sanitize_name(name: str, max_length: int = 64) -> str:
        """Sanitize name to be safe for MCP usage."""
        # Replace non-alphanumeric characters with underscores
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        
        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = f"_{sanitized}"
            
        # Truncate to max length
        return sanitized[:max_length]
    
    @staticmethod
    def sanitize_tool_name(name: str, server_prefix: str = None, max_length: int = 64) -> str:
        """Sanitize tool name with optional server prefix."""
        if server_prefix:
            prefixed_name = f"{server_prefix}_{name}"
            return NameSanitizer.sanitize_name(prefixed_name, max_length)
        return NameSanitizer.sanitize_name(name, max_length)
    
    @staticmethod
    def sanitize_resource_name(name: str, server_prefix: str = None, max_length: int = 64) -> str:
        """Sanitize resource name with optional server prefix."""
        if server_prefix:
            prefixed_name = f"{server_prefix}_{name}"
            return NameSanitizer.sanitize_name(prefixed_name, max_length)
        return NameSanitizer.sanitize_name(name, max_length)


class ResourceNameProcessor:
    """Processes resource names for CRUD operation detection."""
    
    @staticmethod
    def singularize_resource(resource: str) -> str:
        """Convert plural resource names to singular form."""
        if resource.endswith("ies"):
            return resource[:-3] + "y"
        elif resource.endswith("sses"):
            return resource  # Keep as-is for words like "classes"
        elif resource.endswith("s") and not resource.endswith("ss"):
            return resource[:-1]
        return resource