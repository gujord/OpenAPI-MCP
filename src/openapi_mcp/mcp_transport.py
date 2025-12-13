# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

"""
MCP-compliant HTTP Stream Transport implementation.
Follows the official MCP specification for HTTP streaming transport.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from starlette.applications import Starlette
from starlette.responses import StreamingResponse, JSONResponse
from starlette.requests import Request
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Route
import uvicorn

try:
    from .exceptions import RequestExecutionError, ParameterError
except ImportError:
    from exceptions import RequestExecutionError, ParameterError


@dataclass
class MCPSession:
    """Represents an MCP session with unique session ID."""
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    message_history: List[Dict[str, Any]] = field(default_factory=list)
    active: bool = True
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()
    
    def add_message(self, message: Dict[str, Any]):
        """Add message to history."""
        self.message_history.append({
            **message,
            "timestamp": time.time()
        })
    
    def is_expired(self, max_age: int = 3600) -> bool:
        """Check if session is expired."""
        return (time.time() - self.last_activity) > max_age


class MCPTransportMode(Enum):
    """MCP transport response modes."""
    BATCH = "batch"
    STREAMING = "streaming"


class MCPHttpTransport:
    """
    MCP-compliant HTTP Stream Transport.
    
    Implements the official MCP HTTP streaming transport specification:
    - Single HTTP endpoint for all MCP communication
    - JSON-RPC 2.0 message format
    - Session management with unique session IDs
    - Batch and streaming response modes
    - Server-Sent Events for streaming responses
    """
    
    def __init__(
        self,
        mcp_server,
        host: str = "127.0.0.1",
        port: int = 8000,
        cors_origins: List[str] = None,
        message_size_limit: str = "4mb",
        batch_timeout: int = 30,
        session_timeout: int = 3600
    ):
        self.mcp_server = mcp_server
        self.host = host
        self.port = port
        self.cors_origins = cors_origins or ["*"]
        self.message_size_limit = message_size_limit
        self.batch_timeout = batch_timeout
        self.session_timeout = session_timeout
        
        # Session management
        self.sessions: Dict[str, MCPSession] = {}
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Create Starlette app
        self.app = self._create_app()
        self.server = None
        
        logging.info(f"MCP HTTP Transport initialized on {host}:{port}")
    
    def _create_app(self) -> Starlette:
        """Create the Starlette application with MCP endpoints."""
        
        routes = [
            # Standard MCP endpoints for mcp-remote clients
            Route("/mcp", self._handle_mcp_request, methods=["POST", "OPTIONS"]),
            Route("/sse", self._handle_mcp_sse, methods=["GET"]),  # mcp-remote SSE endpoint
            
            # Session-based endpoints (fallback)
            Route("/mcp/sse/{session_id}", self._handle_sse_stream, methods=["GET"]),
            Route("/mcp/sessions/{session_id}", self._handle_session_delete, methods=["DELETE"]),
            
            # Health and info endpoints
            Route("/mcp/health", self._handle_health, methods=["GET"]),
            Route("/health", self._handle_health, methods=["GET"]),  # Alternative health endpoint
        ]
        
        app = Starlette(routes=routes)
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )
        
        return app
    
    async def _handle_mcp_request(self, request: Request):
        """
        Handle MCP JSON-RPC requests via HTTP POST.
        
        This is the main endpoint for all MCP communication.
        Supports both batch and streaming response modes.
        """
        if request.method == "OPTIONS":
            return JSONResponse({"status": "ok"})
        
        try:
            # Get or create session
            session_id = request.headers.get("Mcp-Session-Id")
            if not session_id:
                session_id = str(uuid.uuid4())
                session = MCPSession(session_id=session_id)
                self.sessions[session_id] = session
            else:
                session = self.sessions.get(session_id)
                if not session or not session.active:
                    return JSONResponse(
                        {"error": "Invalid or expired session"},
                        status_code=404
                    )
            
            session.update_activity()
            
            # Parse JSON-RPC request
            body = await request.body()
            if len(body) > self._parse_size_limit():
                return JSONResponse(
                    {"error": "Request too large"},
                    status_code=413
                )
            
            try:
                rpc_request = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError as e:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32700,
                            "message": "Parse error",
                            "data": str(e)
                        }
                    },
                    status_code=400
                )
            
            # Add to session history
            session.add_message(rpc_request)
            
            # Determine response mode from request headers or query params
            response_mode = self._get_response_mode(request)
            
            if response_mode == MCPTransportMode.STREAMING:
                # Return streaming response info
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": rpc_request.get("id"),
                    "result": {
                        "session_id": session_id,
                        "stream_url": f"/mcp/sse/{session_id}",
                        "transport_mode": "streaming"
                    }
                }, headers={"Mcp-Session-Id": session_id})
            else:
                # Handle batch mode - process request immediately
                response = await self._process_mcp_request(rpc_request, session)
                session.add_message(response)
                
                return JSONResponse(
                    response,
                    headers={"Mcp-Session-Id": session_id}
                )
                
        except Exception as e:
            logging.error(f"MCP request handling error: {e}")
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e)
                    }
                },
                status_code=500
            )
    
    async def _handle_sse_stream(self, request: Request):
        """
        Handle Server-Sent Events stream for MCP responses.
        
        Streams JSON-RPC responses via SSE according to MCP specification.
        """
        session_id = request.path_params["session_id"]
        session = self.sessions.get(session_id)
        
        if not session or not session.active:
            return JSONResponse(
                {"error": "Invalid or expired session"},
                status_code=404
            )
        
        session.update_activity()
        
        async def event_generator():
            """Generate SSE events with MCP JSON-RPC responses."""
            
            # Send connection established event
            yield self._format_sse_event(
                "connected",
                {
                    "session_id": session_id,
                    "transport": "mcp-http-sse",
                    "connected_at": time.time()
                }
            )
            
            try:
                # Wait for requests to process
                last_processed = len(session.message_history)
                
                while session.active:
                    # Check for new messages to process
                    current_messages = len(session.message_history)
                    
                    if current_messages > last_processed:
                        # Process new messages
                        for i in range(last_processed, current_messages):
                            message = session.message_history[i]
                            
                            # Skip responses (only process requests)
                            if "method" in message:
                                try:
                                    response = await self._process_mcp_request(message, session)
                                    session.add_message(response)
                                    
                                    # Send response via SSE
                                    yield self._format_sse_event("message", response)
                                    
                                except Exception as e:
                                    error_response = {
                                        "jsonrpc": "2.0",
                                        "id": message.get("id"),
                                        "error": {
                                            "code": -32603,
                                            "message": "Internal error",
                                            "data": str(e)
                                        }
                                    }
                                    session.add_message(error_response)
                                    yield self._format_sse_event("error", error_response)
                        
                        last_processed = len(session.message_history)
                    
                    # Send heartbeat
                    yield self._format_sse_event(
                        "heartbeat",
                        {"timestamp": time.time(), "session_id": session_id}
                    )
                    
                    # Wait before next check
                    await asyncio.sleep(1)
                    
            except asyncio.CancelledError:
                logging.info(f"SSE stream cancelled for session {session_id}")
            except Exception as e:
                logging.error(f"SSE stream error for session {session_id}: {e}")
                yield self._format_sse_event(
                    "error",
                    {"error": str(e), "session_id": session_id}
                )
            finally:
                # Send disconnect event
                yield self._format_sse_event(
                    "disconnected",
                    {"session_id": session_id, "disconnected_at": time.time()}
                )
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Mcp-Session-Id": session_id
            }
        )
    
    async def _handle_session_delete(self, request: Request):
        """Handle session termination via DELETE request."""
        session_id = request.path_params["session_id"]
        
        if session_id in self.sessions:
            self.sessions[session_id].active = False
            del self.sessions[session_id]
            logging.info(f"Session {session_id} terminated")
            return JSONResponse({"status": "terminated"})
        
        return JSONResponse({"error": "Session not found"}, status_code=404)
    
    async def _handle_health(self, request: Request):
        """Health check endpoint."""
        return JSONResponse({
            "status": "healthy",
            "transport": "mcp-http-sse",
            "active_sessions": len([s for s in self.sessions.values() if s.active]),
            "total_sessions": len(self.sessions),
            "uptime": time.time() - getattr(self, '_start_time', time.time())
        })
    
    async def _handle_mcp_sse(self, request: Request):
        """
        Handle MCP SSE endpoint for mcp-remote clients.
        
        This is the standard /sse endpoint that mcp-remote expects for 
        Server-Sent Events communication.
        """
        # Create a new session for this SSE connection
        session_id = str(uuid.uuid4())
        session = MCPSession(session_id=session_id)
        self.sessions[session_id] = session
        session.update_activity()
        
        async def mcp_sse_generator():
            """Generate MCP-compliant SSE events for mcp-remote clients."""
            
            # Send connection established event
            yield self._format_sse_event(
                "connected",
                {
                    "transport": "mcp-http-sse",
                    "session_id": session_id,
                    "server_info": {
                        "name": self.mcp_server.server_name,
                        "version": "1.0.0"
                    },
                    "connected_at": time.time()
                }
            )
            
            try:
                # Wait for incoming JSON-RPC requests via query params or websocket
                # For mcp-remote, requests come via the main /mcp endpoint
                # and this SSE stream returns the responses
                
                last_processed = 0
                heartbeat_counter = 0
                
                while session.active:
                    # Check for new messages to process
                    current_messages = len(session.message_history)
                    
                    if current_messages > last_processed:
                        # Process new messages since last check
                        for i in range(last_processed, current_messages):
                            message = session.message_history[i]
                            
                            # Only send responses (skip requests in history)
                            if "result" in message or "error" in message:
                                yield self._format_sse_event("response", message)
                        
                        last_processed = current_messages
                    
                    # Send heartbeat every 30 seconds
                    heartbeat_counter += 1
                    if heartbeat_counter >= 30:
                        yield self._format_sse_event(
                            "heartbeat",
                            {"timestamp": time.time(), "session_id": session_id}
                        )
                        heartbeat_counter = 0
                    
                    # Wait before next check
                    await asyncio.sleep(1)
                    
            except asyncio.CancelledError:
                logging.info(f"MCP SSE stream cancelled for session {session_id}")
            except Exception as e:
                logging.error(f"MCP SSE stream error for session {session_id}: {e}")
                yield self._format_sse_event(
                    "error",
                    {"error": str(e), "session_id": session_id}
                )
            finally:
                # Clean up session
                if session_id in self.sessions:
                    self.sessions[session_id].active = False
                    del self.sessions[session_id]
                
                # Send disconnect event
                yield self._format_sse_event(
                    "disconnected",
                    {"session_id": session_id, "disconnected_at": time.time()}
                )
        
        return StreamingResponse(
            mcp_sse_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Mcp-Session-Id": session_id
            }
        )
    
    async def _process_mcp_request(self, rpc_request: Dict[str, Any], session: MCPSession) -> Dict[str, Any]:
        """
        Process an MCP JSON-RPC request using the MCP server.
        
        Routes the request to the appropriate MCP server method.
        """
        method = rpc_request.get("method")
        params = rpc_request.get("params", {})
        request_id = rpc_request.get("id")
        
        try:
            # Route to appropriate MCP server method
            if method == "initialize":
                return self.mcp_server._initialize_tool(req_id=request_id, **params)
            elif method == "tools/list":
                return self.mcp_server._tools_list_tool(req_id=request_id)
            elif method == "tools/call":
                return self.mcp_server._tools_call_tool(
                    req_id=request_id,
                    name=params.get("name"),
                    arguments=params.get("arguments", {})
                )
            elif method == "resources/list":
                # Return resources list
                resources = []
                if hasattr(self.mcp_server, 'resource_manager') and self.mcp_server.resource_manager:
                    for name, data in self.mcp_server.resource_manager.registered_resources.items():
                        resources.append({
                            "uri": f"/resource/{name}",
                            "name": name,
                            "description": data["metadata"]["description"],
                            "mimeType": "application/json"
                        })
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"resources": resources}
                }
            elif method == "prompts/list":
                # Return prompts list (if implemented)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"prompts": []}
                }
            else:
                # Unknown method
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
                
        except Exception as e:
            logging.error(f"Error processing MCP request {method}: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }
    
    def _get_response_mode(self, request: Request) -> MCPTransportMode:
        """Determine response mode from request headers or query parameters."""
        # Check for streaming preference in headers
        if request.headers.get("Accept") == "text/event-stream":
            return MCPTransportMode.STREAMING
        
        # Check query parameter
        if request.query_params.get("mode") == "streaming":
            return MCPTransportMode.STREAMING
        
        # Default to batch mode
        return MCPTransportMode.BATCH
    
    def _format_sse_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        event_id: Optional[str] = None
    ) -> str:
        """Format data as Server-Sent Event."""
        lines = []
        
        if event_id:
            lines.append(f"id: {event_id}")
        
        lines.append(f"event: {event_type}")
        
        # Format data as JSON
        data_json = json.dumps(data)
        for line in data_json.split('\n'):
            lines.append(f"data: {line}")
        
        lines.append("")  # Empty line ends the event
        return '\n'.join(lines) + '\n'
    
    def _parse_size_limit(self) -> int:
        """Parse message size limit from string format."""
        size_str = self.message_size_limit.lower()
        if size_str.endswith('mb'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('kb'):
            return int(size_str[:-2]) * 1024
        else:
            return int(size_str)
    
    async def _cleanup_sessions(self):
        """Periodic cleanup of expired sessions."""
        while True:
            try:
                current_time = time.time()
                expired_sessions = []
                
                for session_id, session in self.sessions.items():
                    if session.is_expired(self.session_timeout):
                        expired_sessions.append(session_id)
                
                for session_id in expired_sessions:
                    self.sessions[session_id].active = False
                    del self.sessions[session_id]
                    logging.info(f"Cleaned up expired session: {session_id}")
                
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Session cleanup error: {e}")
                await asyncio.sleep(300)
    
    async def start(self):
        """Start the MCP HTTP transport server."""
        self._start_time = time.time()
        
        # Start session cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_sessions())
        
        # Create and start Uvicorn server
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        self.server = uvicorn.Server(config)
        
        logging.info(f"Starting MCP HTTP transport server on {self.host}:{self.port}")
        await self.server.serve()
    
    async def stop(self):
        """Stop the MCP HTTP transport server."""
        if self.cleanup_task:
            self.cleanup_task.cancel()
        
        if self.server:
            self.server.should_exit = True
        
        # Cleanup all sessions
        for session in self.sessions.values():
            session.active = False
        self.sessions.clear()
        
        logging.info("MCP HTTP transport server stopped")
    
    def get_transport_info(self) -> Dict[str, Any]:
        """Get transport information and status."""
        return {
            "type": "mcp-http-sse",
            "host": self.host,
            "port": self.port,
            "endpoints": {
                "mcp": "/mcp",
                "sse": "/sse",  # Standard mcp-remote endpoint
                "sse_session": "/mcp/sse/{session_id}",
                "session_delete": "/mcp/sessions/{session_id}",
                "health": "/health"
            },
            "active_sessions": len([s for s in self.sessions.values() if s.active]),
            "total_sessions": len(self.sessions),
            "message_size_limit": self.message_size_limit,
            "batch_timeout": self.batch_timeout,
            "session_timeout": self.session_timeout
        }