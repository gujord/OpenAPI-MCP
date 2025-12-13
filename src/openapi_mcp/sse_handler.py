# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

__all__ = [
    "SSEEventType",
    "SSEEvent",
    "SSEConnection",
    "SSEStreamProcessor",
    "SSEManager",
    "SSEToolFactory",
    "ChunkProcessors",
]

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, AsyncGenerator, Callable
from dataclasses import dataclass
from enum import Enum
import httpx

try:
    from .exceptions import RequestExecutionError, ParameterError
except ImportError:
    from exceptions import RequestExecutionError, ParameterError


class SSEEventType(Enum):
    """Types of SSE events."""
    DATA = "data"
    ERROR = "error"
    COMPLETE = "complete"
    HEARTBEAT = "heartbeat"
    METADATA = "metadata"


@dataclass
class SSEEvent:
    """Represents a Server-Sent Event."""
    type: SSEEventType
    data: Any
    id: Optional[str] = None
    retry: Optional[int] = None
    timestamp: Optional[float] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_sse_format(self) -> str:
        """Convert to SSE wire format."""
        lines = []
        
        if self.id:
            lines.append(f"id: {self.id}")
        
        lines.append(f"event: {self.type.value}")
        
        if isinstance(self.data, (dict, list)):
            data_str = json.dumps(self.data)
        else:
            data_str = str(self.data)
        
        # Handle multi-line data
        for line in data_str.split('\n'):
            lines.append(f"data: {line}")
        
        if self.retry:
            lines.append(f"retry: {self.retry}")
        
        lines.append("")  # Empty line to end the event
        return '\n'.join(lines) + '\n'


class SSEConnection:
    """Manages an individual SSE connection."""
    
    def __init__(self, connection_id: str, heartbeat_interval: int = 30):
        self.connection_id = connection_id
        self.heartbeat_interval = heartbeat_interval
        self.connected = True
        self.last_heartbeat = time.time()
        self._event_queue = asyncio.Queue()
        self._heartbeat_task = None
    
    async def send_event(self, event: SSEEvent) -> None:
        """Send an event to this connection."""
        if self.connected:
            await self._event_queue.put(event)
    
    async def event_stream(self) -> AsyncGenerator[str, None]:
        """Generate SSE events for this connection."""
        try:
            # Start heartbeat task
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            # Send initial connection event
            await self.send_event(SSEEvent(
                type=SSEEventType.METADATA,
                data={"connected": True, "connection_id": self.connection_id},
                id=f"conn_{self.connection_id}"
            ))
            
            while self.connected:
                try:
                    # Wait for events with timeout for heartbeat
                    event = await asyncio.wait_for(
                        self._event_queue.get(), 
                        timeout=self.heartbeat_interval / 2
                    )
                    yield event.to_sse_format()
                except asyncio.TimeoutError:
                    # Send heartbeat if no events
                    if time.time() - self.last_heartbeat > self.heartbeat_interval:
                        await self._send_heartbeat()
                
        except Exception as e:
            logging.error(f"SSE connection {self.connection_id} error: {e}")
            await self.send_event(SSEEvent(
                type=SSEEventType.ERROR,
                data={"error": str(e)}
            ))
        finally:
            await self.disconnect()
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat events."""
        while self.connected:
            await asyncio.sleep(self.heartbeat_interval)
            if self.connected:
                await self._send_heartbeat()
    
    async def _send_heartbeat(self):
        """Send a heartbeat event."""
        self.last_heartbeat = time.time()
        await self._event_queue.put(SSEEvent(
            type=SSEEventType.HEARTBEAT,
            data={"timestamp": self.last_heartbeat}
        ))
    
    async def disconnect(self):
        """Disconnect this SSE connection."""
        self.connected = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        
        # Send final event
        try:
            await self._event_queue.put(SSEEvent(
                type=SSEEventType.COMPLETE,
                data={"disconnected": True}
            ))
        except:
            pass


class SSEStreamProcessor:
    """Processes streaming responses and converts them to SSE events."""
    
    def __init__(self, connection: SSEConnection):
        self.connection = connection
        self.chunk_count = 0
    
    async def process_stream(
        self, 
        response: httpx.Response,
        chunk_processor: Optional[Callable[[bytes], Dict[str, Any]]] = None
    ) -> None:
        """Process a streaming HTTP response and send SSE events."""
        try:
            # Send metadata about the stream
            await self.connection.send_event(SSEEvent(
                type=SSEEventType.METADATA,
                data={
                    "stream_started": True,
                    "content_type": response.headers.get("content-type"),
                    "status_code": response.status_code,
                    "headers": dict(response.headers)
                }
            ))
            
            # Process the stream
            async for chunk in response.aiter_bytes(chunk_size=1024):
                if not self.connection.connected:
                    break
                
                self.chunk_count += 1
                
                # Process chunk if processor provided
                if chunk_processor:
                    try:
                        processed_data = chunk_processor(chunk)
                        await self.connection.send_event(SSEEvent(
                            type=SSEEventType.DATA,
                            data=processed_data,
                            id=f"chunk_{self.chunk_count}"
                        ))
                    except Exception as e:
                        logging.warning(f"Chunk processing error: {e}")
                        await self.connection.send_event(SSEEvent(
                            type=SSEEventType.DATA,
                            data={"raw_chunk": chunk.decode('utf-8', errors='ignore')},
                            id=f"chunk_{self.chunk_count}"
                        ))
                else:
                    # Send raw chunk
                    await self.connection.send_event(SSEEvent(
                        type=SSEEventType.DATA,
                        data={"chunk": chunk.decode('utf-8', errors='ignore')},
                        id=f"chunk_{self.chunk_count}"
                    ))
            
            # Send completion event
            await self.connection.send_event(SSEEvent(
                type=SSEEventType.COMPLETE,
                data={
                    "stream_complete": True,
                    "total_chunks": self.chunk_count
                }
            ))
            
        except Exception as e:
            logging.error(f"Stream processing error: {e}")
            await self.connection.send_event(SSEEvent(
                type=SSEEventType.ERROR,
                data={"error": str(e), "chunk_count": self.chunk_count}
            ))


class SSEManager:
    """Manages multiple SSE connections and streaming operations."""
    
    def __init__(self):
        self.connections: Dict[str, SSEConnection] = {}
        self.connection_counter = 0
    
    def create_connection(self, heartbeat_interval: int = 30) -> SSEConnection:
        """Create a new SSE connection."""
        self.connection_counter += 1
        connection_id = f"sse_{self.connection_counter}_{int(time.time())}"
        
        connection = SSEConnection(connection_id, heartbeat_interval)
        self.connections[connection_id] = connection
        
        logging.info(f"Created SSE connection: {connection_id}")
        return connection
    
    async def remove_connection(self, connection_id: str) -> None:
        """Remove an SSE connection."""
        if connection_id in self.connections:
            connection = self.connections[connection_id]
            await connection.disconnect()
            del self.connections[connection_id]
            logging.info(f"Removed SSE connection: {connection_id}")
    
    async def broadcast_to_all(self, event: SSEEvent) -> None:
        """Broadcast an event to all connected clients."""
        disconnected = []
        
        for connection_id, connection in self.connections.items():
            try:
                if connection.connected:
                    await connection.send_event(event)
                else:
                    disconnected.append(connection_id)
            except Exception as e:
                logging.error(f"Error broadcasting to {connection_id}: {e}")
                disconnected.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected:
            await self.remove_connection(connection_id)
    
    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        active_count = sum(1 for conn in self.connections.values() if conn.connected)
        return active_count
    
    async def cleanup_stale_connections(self, max_age: int = 300) -> None:
        """Clean up stale connections older than max_age seconds."""
        current_time = time.time()
        stale_connections = []
        
        for connection_id, connection in self.connections.items():
            if current_time - connection.last_heartbeat > max_age:
                stale_connections.append(connection_id)
        
        for connection_id in stale_connections:
            await self.remove_connection(connection_id)
            logging.info(f"Cleaned up stale connection: {connection_id}")


class SSEToolFactory:
    """Factory for creating SSE-enabled tools."""
    
    def __init__(self, sse_manager: SSEManager):
        self.sse_manager = sse_manager
    
    def create_streaming_tool(
        self, 
        base_tool_func: Callable,
        chunk_processor: Optional[Callable[[bytes], Dict[str, Any]]] = None
    ) -> Callable:
        """Create a streaming version of a tool that supports SSE."""
        
        async def streaming_tool_func(req_id: Any = None, stream: bool = False, **kwargs):
            """Streaming tool function that can return SSE responses."""
            
            if not stream:
                # Use regular tool function for non-streaming requests
                return base_tool_func(req_id=req_id, **kwargs)
            
            try:
                # Create SSE connection
                connection = self.sse_manager.create_connection()
                
                # Prepare the base request (but don't execute yet)
                dry_run_result = base_tool_func(req_id=req_id, dry_run=True, **kwargs)
                
                if 'error' in dry_run_result:
                    await connection.send_event(SSEEvent(
                        type=SSEEventType.ERROR,
                        data=dry_run_result['error']
                    ))
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "stream_connection_id": connection.connection_id,
                            "stream_url": f"/sse/stream/{connection.connection_id}",
                            "error": dry_run_result['error']
                        }
                    }
                
                # Extract request details
                request_info = dry_run_result['result']['request']
                
                # Start streaming task
                asyncio.create_task(
                    self._execute_streaming_request(
                        connection, request_info, chunk_processor
                    )
                )
                
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "stream_connection_id": connection.connection_id,
                        "stream_url": f"/sse/stream/{connection.connection_id}",
                        "request_info": request_info
                    }
                }
                
            except Exception as e:
                logging.error(f"Streaming tool error: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32603,
                        "message": f"Streaming error: {e}"
                    }
                }
        
        return streaming_tool_func
    
    async def _execute_streaming_request(
        self,
        connection: SSEConnection,
        request_info: Dict[str, Any],
        chunk_processor: Optional[Callable[[bytes], Dict[str, Any]]] = None
    ) -> None:
        """Execute the streaming HTTP request."""
        try:
            async with httpx.AsyncClient() as client:
                # Build request
                method = request_info['method']
                url = request_info['url']
                headers = request_info.get('headers', {})
                params = request_info.get('params', {})
                body = request_info.get('body')
                
                # Make streaming request
                async with client.stream(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=body if body else None
                ) as response:
                    
                    response.raise_for_status()
                    
                    # Process the stream
                    processor = SSEStreamProcessor(connection)
                    await processor.process_stream(response, chunk_processor)
                    
        except Exception as e:
            logging.error(f"Streaming request error: {e}")
            await connection.send_event(SSEEvent(
                type=SSEEventType.ERROR,
                data={"error": str(e)}
            ))
        finally:
            await connection.disconnect()


# Common chunk processors
class ChunkProcessors:
    """Collection of common chunk processing functions."""
    
    @staticmethod
    def json_lines_processor(chunk: bytes) -> Dict[str, Any]:
        """Process JSON Lines format."""
        try:
            text = chunk.decode('utf-8').strip()
            if text:
                lines = text.split('\n')
                parsed_lines = []
                for line in lines:
                    if line.strip():
                        parsed_lines.append(json.loads(line))
                return {"json_lines": parsed_lines}
        except Exception as e:
            return {"error": f"JSON Lines parsing error: {e}", "raw": chunk.decode('utf-8', errors='ignore')}
    
    @staticmethod
    def text_processor(chunk: bytes) -> Dict[str, Any]:
        """Process plain text chunks."""
        return {"text": chunk.decode('utf-8', errors='ignore')}
    
    @staticmethod
    def csv_processor(chunk: bytes) -> Dict[str, Any]:
        """Process CSV chunks."""
        try:
            text = chunk.decode('utf-8').strip()
            if text:
                lines = text.split('\n')
                return {"csv_lines": lines}
        except Exception as e:
            return {"error": f"CSV parsing error: {e}", "raw": chunk.decode('utf-8', errors='ignore')}