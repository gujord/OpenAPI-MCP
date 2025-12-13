# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP


class MCPServerError(Exception):
    """Base exception for MCP server errors."""
    
    def __init__(self, message: str, code: int = -32603):
        super().__init__(message)
        self.message = message
        self.code = code
    
    def to_json_rpc_error(self, req_id=None):
        """Convert to JSON-RPC error format."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": self.code,
                "message": self.message
            }
        }


class OpenAPIError(MCPServerError):
    """Raised when OpenAPI spec loading or parsing fails."""
    
    def __init__(self, message: str):
        super().__init__(f"OpenAPI Error: {message}", -32600)


class AuthenticationError(MCPServerError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str):
        super().__init__(f"Authentication Error: {message}", -32401)


class ParameterError(MCPServerError):
    """Raised when parameter validation or parsing fails."""
    
    def __init__(self, message: str):
        super().__init__(f"Parameter Error: {message}", -32602)


class ToolNotFoundError(MCPServerError):
    """Raised when a requested tool is not found."""
    
    def __init__(self, tool_name: str, suggestion: str = None):
        message = f"Tool '{tool_name}' not found"
        if suggestion:
            message += f". Did you mean '{suggestion}'?"
        super().__init__(message, -32601)


class RequestExecutionError(MCPServerError):
    """Raised when HTTP request execution fails."""
    
    def __init__(self, message: str):
        super().__init__(f"Request Execution Error: {message}", -32603)


class ConfigurationError(MCPServerError):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str):
        super().__init__(f"Configuration Error: {message}", -32000)