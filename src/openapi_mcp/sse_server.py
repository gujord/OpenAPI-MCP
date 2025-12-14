# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

__all__ = ["SSEHTTPServer", "SSEServerManager", "create_sse_enabled_server"]

import asyncio
import json
import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from starlette.applications import Starlette
from starlette.responses import StreamingResponse, JSONResponse, Response
from starlette.routing import Route
from starlette.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import uvicorn

try:
    from .sse_handler import SSEManager, SSEEvent, SSEEventType
    from .exceptions import RequestExecutionError
except ImportError:
    from sse_handler import SSEManager, SSEEvent, SSEEventType
    from exceptions import RequestExecutionError


class SSEHTTPServer:
    """HTTP server for serving SSE endpoints."""

    def __init__(self, sse_manager: SSEManager, host: str = "127.0.0.1", port: int = 8000):
        self.sse_manager = sse_manager
        self.host = host
        self.port = port
        self.app = None
        self.server = None
        self._shutdown_event = asyncio.Event()

    def create_app(self) -> Starlette:
        """Create the Starlette application."""

        @asynccontextmanager
        async def lifespan(app):
            """Application lifespan manager."""
            logging.info(f"SSE HTTP Server starting on {self.host}:{self.port}")
            # Start cleanup task
            cleanup_task = asyncio.create_task(self._cleanup_loop())
            try:
                yield
            finally:
                logging.info("SSE HTTP Server shutting down")
                cleanup_task.cancel()
                # Disconnect all connections
                for connection in list(self.sse_manager.connections.values()):
                    await connection.disconnect()

        # Define routes
        routes = [
            Route("/sse/stream/{connection_id}", self.sse_stream_endpoint),
            Route("/sse/connections", self.sse_connections_endpoint),
            Route("/sse/health", self.health_endpoint),
            Route("/sse/broadcast", self.broadcast_endpoint, methods=["POST"]),
        ]

        app = Starlette(routes=routes, lifespan=lifespan)

        # Add CORS middleware with secure defaults (localhost only)
        default_origins = [
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080",
        ]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=default_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        return app

    async def sse_stream_endpoint(self, request):
        """SSE streaming endpoint."""
        connection_id = request.path_params["connection_id"]

        # Get the connection
        connection = self.sse_manager.connections.get(connection_id)
        if not connection:
            return JSONResponse({"error": f"Connection {connection_id} not found"}, status_code=404)

        if not connection.connected:
            return JSONResponse({"error": f"Connection {connection_id} already disconnected"}, status_code=410)

        async def event_generator():
            """Generate SSE events for the client."""
            try:
                async for event_data in connection.event_stream():
                    yield event_data
            except Exception as e:
                logging.error(f"SSE stream error for {connection_id}: {e}")
                # Send error event
                error_event = SSEEvent(type=SSEEventType.ERROR, data={"error": str(e)})
                yield error_event.to_sse_format()
            finally:
                # Clean up connection
                await self.sse_manager.remove_connection(connection_id)

        return EventSourceResponse(event_generator())

    async def sse_connections_endpoint(self, request):
        """Get information about active SSE connections."""
        connections_info = []

        for connection_id, connection in self.sse_manager.connections.items():
            connections_info.append(
                {
                    "connection_id": connection_id,
                    "connected": connection.connected,
                    "last_heartbeat": connection.last_heartbeat,
                    "heartbeat_interval": connection.heartbeat_interval,
                }
            )

        return JSONResponse({"active_connections": len(connections_info), "connections": connections_info})

    async def health_endpoint(self, request):
        """Health check endpoint."""
        return JSONResponse(
            {
                "status": "healthy",
                "active_connections": self.sse_manager.get_connection_count(),
                "server": "SSE HTTP Server",
                "version": "1.0.0",
            }
        )

    async def broadcast_endpoint(self, request):
        """Broadcast a message to all connected clients."""
        try:
            data = await request.json()

            event = SSEEvent(type=SSEEventType.DATA, data=data.get("data", {}), id=data.get("id"))

            await self.sse_manager.broadcast_to_all(event)

            return JSONResponse(
                {
                    "success": True,
                    "broadcasted_to": self.sse_manager.get_connection_count(),
                    "message": "Event broadcasted successfully",
                }
            )

        except Exception as e:
            logging.error(f"Broadcast error: {e}")
            return JSONResponse({"error": str(e)}, status_code=400)

    async def _cleanup_loop(self):
        """Periodic cleanup of stale connections."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self.sse_manager.cleanup_stale_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Cleanup error: {e}")

    async def start_server(self):
        """Start the SSE HTTP server."""
        self.app = self.create_app()

        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="info", access_log=True)

        self.server = uvicorn.Server(config)

        # Set up signal handlers
        def signal_handler(signum, frame):
            logging.info(f"Received signal {signum}, shutting down...")
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start server
        try:
            await self.server.serve()
        except Exception as e:
            logging.error(f"Server error: {e}")
        finally:
            await self._shutdown()

    async def _shutdown(self):
        """Shutdown the server gracefully."""
        if self.server:
            self.server.should_exit = True

        # Disconnect all SSE connections
        for connection in list(self.sse_manager.connections.values()):
            await connection.disconnect()

        logging.info("SSE HTTP Server shutdown complete")

    def run(self):
        """Run the server (blocking)."""
        try:
            asyncio.run(self.start_server())
        except KeyboardInterrupt:
            logging.info("Server interrupted by user")
        except Exception as e:
            logging.error(f"Server failed: {e}")
            sys.exit(1)


class SSEServerManager:
    """Manages the SSE server lifecycle alongside the MCP server."""

    def __init__(self, sse_manager: SSEManager, host: str = "127.0.0.1", port: int = 8000):
        self.sse_manager = sse_manager
        self.sse_server = SSEHTTPServer(sse_manager, host, port)
        self.server_task = None
        self.running = False

    async def start(self):
        """Start the SSE server in the background."""
        if not self.running:
            self.server_task = asyncio.create_task(self.sse_server.start_server())
            self.running = True
            logging.info(f"SSE server started on {self.sse_server.host}:{self.sse_server.port}")

    async def stop(self):
        """Stop the SSE server."""
        if self.running and self.server_task:
            self.server_task.cancel()
            await self.sse_server._shutdown()
            self.running = False
            logging.info("SSE server stopped")

    def get_stream_url(self, connection_id: str) -> str:
        """Get the SSE stream URL for a connection."""
        return f"http://{self.sse_server.host}:{self.sse_server.port}/sse/stream/{connection_id}"

    def get_connections_url(self) -> str:
        """Get the SSE connections info URL."""
        return f"http://{self.sse_server.host}:{self.sse_server.port}/sse/connections"

    def get_health_url(self) -> str:
        """Get the health check URL."""
        return f"http://{self.sse_server.host}:{self.sse_server.port}/sse/health"


def create_sse_enabled_server(sse_manager: SSEManager, host: str = "127.0.0.1", port: int = 8000) -> SSEServerManager:
    """Factory function to create an SSE-enabled server manager."""
    return SSEServerManager(sse_manager, host, port)
