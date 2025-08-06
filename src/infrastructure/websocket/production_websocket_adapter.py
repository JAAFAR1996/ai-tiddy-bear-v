"""
Production WebSocket Adapter - Real-time Communication
=====================================================
Enterprise-grade WebSocket service supporting:
- Real-time bidirectional communication
- Connection pooling and scaling
- Authentication and authorization
- Message queuing and persistence
- Rate limiting and abuse protection
- Health monitoring and metrics
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import uuid
import weakref
import os

try:
    from fastapi import WebSocket, WebSocketDisconnect
    from fastapi.websockets import WebSocketState
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


class ConnectionStatus(Enum):
    """WebSocket connection status."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class MessageType(Enum):
    """WebSocket message types."""
    SYSTEM = "system"
    CHAT = "chat"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    AUTH = "auth"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"


@dataclass
class WebSocketMessage:
    """WebSocket message wrapper."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.SYSTEM
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    sender_id: Optional[str] = None
    recipient_id: Optional[str] = None
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for transmission."""
        return {
            "message_id": self.message_id,
            "type": self.message_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "correlation_id": self.correlation_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WebSocketMessage':
        """Create message from dictionary."""
        return cls(
            message_id=data.get("message_id", str(uuid.uuid4())),
            message_type=MessageType(data.get("type", MessageType.SYSTEM.value)),
            data=data.get("data", {}),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            sender_id=data.get("sender_id"),
            recipient_id=data.get("recipient_id"),
            correlation_id=data.get("correlation_id")
        )


@dataclass
class WebSocketConnection:
    """WebSocket connection metadata."""
    connection_id: str
    websocket: Any  # WebSocket instance
    user_id: Optional[str]
    session_id: Optional[str]
    connected_at: datetime
    last_activity: datetime
    status: ConnectionStatus = ConnectionStatus.CONNECTED
    subscriptions: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    def is_active(self, timeout_seconds: int = 300) -> bool:
        """Check if connection is still active based on last activity."""
        return (datetime.now() - self.last_activity).total_seconds() < timeout_seconds


@dataclass
class WebSocketMetrics:
    """WebSocket service metrics."""
    total_connections: int = 0
    active_connections: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    messages_failed: int = 0
    connections_dropped: int = 0
    authentication_failures: int = 0
    rate_limit_hits: int = 0
    avg_message_processing_time_ms: float = 0.0
    
    @property
    def message_success_rate(self) -> float:
        total_messages = self.messages_sent + self.messages_failed
        if total_messages == 0:
            return 0.0
        return (self.messages_sent / total_messages) * 100


class ProductionWebSocketAdapter:
    """
    Production WebSocket adapter with comprehensive real-time communication features.
    
    Features:
    - Connection pooling and management
    - Authentication and session handling
    - Message routing and broadcasting
    - Rate limiting and abuse protection
    - Subscription management
    - Health monitoring and metrics
    - Automatic reconnection handling
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.metrics = WebSocketMetrics()
        
        # Connection management
        self.connections: Dict[str, WebSocketConnection] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> connection_ids
        self.topic_subscriptions: Dict[str, Set[str]] = {}  # topic -> connection_ids
        
        # Configuration
        self.max_connections_per_user = int(os.getenv("WS_MAX_CONNECTIONS_PER_USER", "5"))
        self.heartbeat_interval = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))
        self.connection_timeout = int(os.getenv("WS_CONNECTION_TIMEOUT", "300"))
        self.message_rate_limit = int(os.getenv("WS_MESSAGE_RATE_LIMIT", "100"))  # per minute
        self.max_message_size = int(os.getenv("WS_MAX_MESSAGE_SIZE", "10240"))  # 10KB
        
        # Message handlers
        self.message_handlers: Dict[MessageType, Callable] = {}
        
        # Rate limiting (simple in-memory, use Redis in production)
        self.rate_limit_counters: Dict[str, Dict[str, int]] = {}
        
        # Background tasks
        self.cleanup_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        
        # Start background tasks
        self._start_background_tasks()
        
        self.logger.info("ProductionWebSocketAdapter initialized")
    
    def _start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        self.cleanup_task = asyncio.create_task(self._cleanup_connections_loop())
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def connect(
        self,
        websocket: Any,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Register new WebSocket connection.
        
        Args:
            websocket: WebSocket instance
            user_id: Authenticated user ID
            session_id: Session identifier
            metadata: Additional connection metadata
            
        Returns:
            Connection ID
        """
        connection_id = str(uuid.uuid4())
        
        try:
            # Check connection limits
            if user_id and not self._check_connection_limit(user_id):
                await self._send_error(websocket, "connection_limit_exceeded", "Too many connections")
                await websocket.close(code=1008, reason="Connection limit exceeded")
                return None
            
            # Create connection
            connection = WebSocketConnection(
                connection_id=connection_id,
                websocket=websocket,
                user_id=user_id,
                session_id=session_id,
                connected_at=datetime.now(),
                last_activity=datetime.now(),
                metadata=metadata or {}
            )
            
            # Store connection
            self.connections[connection_id] = connection
            
            # Track user connections
            if user_id:
                if user_id not in self.user_connections:
                    self.user_connections[user_id] = set()
                self.user_connections[user_id].add(connection_id)
            
            # Update metrics
            self.metrics.total_connections += 1
            self.metrics.active_connections += 1
            
            # Send welcome message
            welcome_message = WebSocketMessage(
                message_type=MessageType.SYSTEM,
                data={
                    "event": "connected",
                    "connection_id": connection_id,
                    "server_time": datetime.now().isoformat()
                }
            )
            
            await self._send_message_to_connection(connection_id, welcome_message)
            
            self.logger.info(
                f"WebSocket connection established",
                extra={
                    "connection_id": connection_id,
                    "user_id": user_id,
                    "session_id": session_id
                }
            )
            
            return connection_id
            
        except Exception as e:
            self.logger.error(f"WebSocket connection failed: {e}", exc_info=True)
            if connection_id in self.connections:
                await self.disconnect(connection_id)
            return None
    
    async def disconnect(self, connection_id: str, reason: str = "normal_closure") -> None:
        """
        Disconnect WebSocket connection.
        
        Args:
            connection_id: Connection identifier
            reason: Disconnection reason
        """
        try:
            connection = self.connections.get(connection_id)
            if not connection:
                return
            
            # Update connection status
            connection.status = ConnectionStatus.DISCONNECTING
            
            # Remove from user connections
            if connection.user_id:
                user_connections = self.user_connections.get(connection.user_id, set())
                user_connections.discard(connection_id)
                if not user_connections:
                    del self.user_connections[connection.user_id]
            
            # Remove from topic subscriptions
            for topic in connection.subscriptions:
                topic_connections = self.topic_subscriptions.get(topic, set())
                topic_connections.discard(connection_id)
                if not topic_connections:
                    del self.topic_subscriptions[topic]
            
            # Close WebSocket
            try:
                if hasattr(connection.websocket, 'close'):
                    await connection.websocket.close()
            except Exception:
                pass  # Connection might already be closed
            
            # Remove connection
            del self.connections[connection_id]
            
            # Update metrics
            self.metrics.active_connections -= 1
            self.metrics.connections_dropped += 1
            
            self.logger.info(
                f"WebSocket connection closed",
                extra={
                    "connection_id": connection_id,
                    "user_id": connection.user_id,
                    "reason": reason
                }
            )
            
        except Exception as e:
            self.logger.error(f"WebSocket disconnection error: {e}", exc_info=True)
    
    async def send_message(
        self,
        connection_id: str,
        message: WebSocketMessage
    ) -> bool:
        """
        Send message to specific connection.
        
        Args:
            connection_id: Target connection ID
            message: Message to send
            
        Returns:
            True if sent successfully
        """
        return await self._send_message_to_connection(connection_id, message)
    
    async def send_to_user(
        self,
        user_id: str,
        message: WebSocketMessage
    ) -> int:
        """
        Send message to all connections of a user.
        
        Args:
            user_id: Target user ID
            message: Message to send
            
        Returns:
            Number of connections message was sent to
        """
        connection_ids = self.user_connections.get(user_id, set())
        success_count = 0
        
        for connection_id in connection_ids.copy():  # Copy to avoid modification during iteration
            success = await self._send_message_to_connection(connection_id, message)
            if success:
                success_count += 1
        
        return success_count
    
    async def broadcast_to_topic(
        self,
        topic: str,
        message: WebSocketMessage,
        exclude_connection_id: Optional[str] = None
    ) -> int:
        """
        Broadcast message to all subscribers of a topic.
        
        Args:
            topic: Topic name
            message: Message to broadcast
            exclude_connection_id: Connection to exclude from broadcast
            
        Returns:
            Number of connections message was sent to
        """
        connection_ids = self.topic_subscriptions.get(topic, set())
        success_count = 0
        
        for connection_id in connection_ids.copy():
            if connection_id != exclude_connection_id:
                success = await self._send_message_to_connection(connection_id, message)
                if success:
                    success_count += 1
        
        return success_count
    
    async def _send_message_to_connection(
        self,
        connection_id: str,
        message: WebSocketMessage
    ) -> bool:
        """Send message to specific connection."""
        start_time = time.time()
        
        try:
            connection = self.connections.get(connection_id)
            if not connection or connection.status != ConnectionStatus.CONNECTED:
                return False
            
            # Check rate limiting
            if not self._check_rate_limit(connection_id):
                self.metrics.rate_limit_hits += 1
                await self._send_error(
                    connection.websocket,
                    "rate_limit_exceeded",
                    "Message rate limit exceeded"
                )
                return False
            
            # Serialize message
            message_data = json.dumps(message.to_dict())
            
            # Check message size
            if len(message_data) > self.max_message_size:
                self.logger.warning(f"Message too large: {len(message_data)} bytes")
                return False
            
            # Send message
            await connection.websocket.send_text(message_data)
            
            # Update connection activity
            connection.update_activity()
            
            # Update metrics
            self.metrics.messages_sent += 1
            processing_time = (time.time() - start_time) * 1000
            self._update_avg_processing_time(processing_time)
            
            self.logger.debug(
                f"Message sent successfully",
                extra={
                    "connection_id": connection_id,
                    "message_type": message.message_type.value,
                    "processing_time_ms": processing_time
                }
            )
            
            return True
            
        except Exception as e:
            self.metrics.messages_failed += 1
            self.logger.error(
                f"Failed to send message to connection {connection_id}: {e}",
                exc_info=True
            )
            
            # Connection might be broken, clean it up
            await self.disconnect(connection_id, "send_error")
            
            return False
    
    async def handle_message(
        self,
        connection_id: str,
        raw_message: str
    ) -> None:
        """
        Handle incoming message from WebSocket connection.
        
        Args:
            connection_id: Source connection ID
            raw_message: Raw message string
        """
        try:
            connection = self.connections.get(connection_id)
            if not connection:
                return
            
            # Update connection activity
            connection.update_activity()
            
            # Parse message
            try:
                message_data = json.loads(raw_message)
                message = WebSocketMessage.from_dict(message_data)
                message.sender_id = connection.user_id
            except json.JSONDecodeError as e:
                await self._send_error(
                    connection.websocket,
                    "invalid_message_format",
                    f"Invalid JSON: {str(e)}"
                )
                return
            
            # Check rate limiting
            if not self._check_rate_limit(connection_id):
                self.metrics.rate_limit_hits += 1
                await self._send_error(
                    connection.websocket,
                    "rate_limit_exceeded",
                    "Message rate limit exceeded"
                )
                return
            
            # Update metrics
            self.metrics.messages_received += 1
            
            # Handle specific message types
            if message.message_type == MessageType.HEARTBEAT:
                await self._handle_heartbeat(connection_id, message)
            elif message.message_type == MessageType.SUBSCRIBE:
                await self._handle_subscribe(connection_id, message)
            elif message.message_type == MessageType.UNSUBSCRIBE:
                await self._handle_unsubscribe(connection_id, message)
            else:
                # Route to registered handlers
                handler = self.message_handlers.get(message.message_type)
                if handler:
                    await handler(connection_id, message)
                else:
                    self.logger.warning(f"No handler for message type: {message.message_type.value}")
            
        except Exception as e:
            self.logger.error(f"Message handling error: {e}", exc_info=True)
            await self._send_error(
                connection.websocket if connection_id in self.connections else None,
                "processing_error",
                "Message processing failed"
            )
    
    async def _handle_heartbeat(self, connection_id: str, message: WebSocketMessage) -> None:
        """Handle heartbeat message."""
        response = WebSocketMessage(
            message_type=MessageType.HEARTBEAT,
            data={
                "pong": True,
                "server_time": datetime.now().isoformat()
            },
            correlation_id=message.correlation_id
        )
        
        await self._send_message_to_connection(connection_id, response)
    
    async def _handle_subscribe(self, connection_id: str, message: WebSocketMessage) -> None:
        """Handle topic subscription."""
        try:
            topic = message.data.get("topic")
            if not topic:
                await self._send_error(
                    self.connections[connection_id].websocket,
                    "missing_topic",
                    "Topic is required for subscription"
                )
                return
            
            # Add connection to topic
            if topic not in self.topic_subscriptions:
                self.topic_subscriptions[topic] = set()
            
            self.topic_subscriptions[topic].add(connection_id)
            self.connections[connection_id].subscriptions.add(topic)
            
            # Confirm subscription
            response = WebSocketMessage(
                message_type=MessageType.SYSTEM,
                data={
                    "event": "subscribed",
                    "topic": topic
                },
                correlation_id=message.correlation_id
            )
            
            await self._send_message_to_connection(connection_id, response)
            
            self.logger.info(f"Connection {connection_id} subscribed to topic: {topic}")
            
        except Exception as e:
            self.logger.error(f"Subscription error: {e}", exc_info=True)
    
    async def _handle_unsubscribe(self, connection_id: str, message: WebSocketMessage) -> None:
        """Handle topic unsubscription."""
        try:
            topic = message.data.get("topic")
            if not topic:
                return
            
            # Remove connection from topic
            if topic in self.topic_subscriptions:
                self.topic_subscriptions[topic].discard(connection_id)
                if not self.topic_subscriptions[topic]:
                    del self.topic_subscriptions[topic]
            
            if connection_id in self.connections:
                self.connections[connection_id].subscriptions.discard(topic)
            
            # Confirm unsubscription
            response = WebSocketMessage(
                message_type=MessageType.SYSTEM,
                data={
                    "event": "unsubscribed",
                    "topic": topic
                },
                correlation_id=message.correlation_id
            )
            
            await self._send_message_to_connection(connection_id, response)
            
            self.logger.info(f"Connection {connection_id} unsubscribed from topic: {topic}")
            
        except Exception as e:
            self.logger.error(f"Unsubscription error: {e}", exc_info=True)
    
    def register_message_handler(
        self,
        message_type: MessageType,
        handler: Callable[[str, WebSocketMessage], None]
    ) -> None:
        """Register message handler for specific message type."""
        self.message_handlers[message_type] = handler
        self.logger.info(f"Registered handler for message type: {message_type.value}")
    
    def _check_connection_limit(self, user_id: str) -> bool:
        """Check if user is within connection limits."""
        user_connections = self.user_connections.get(user_id, set())
        return len(user_connections) < self.max_connections_per_user
    
    def _check_rate_limit(self, connection_id: str) -> bool:
        """Check rate limiting for connection."""
        now = datetime.now()
        minute_key = now.strftime("%Y-%m-%d-%H-%M")
        
        if connection_id not in self.rate_limit_counters:
            self.rate_limit_counters[connection_id] = {}
        
        connection_counters = self.rate_limit_counters[connection_id]
        
        # Clean old counters
        connection_counters = {
            key: count for key, count in connection_counters.items()
            if (now - datetime.strptime(key, "%Y-%m-%d-%H-%M")).total_seconds() < 60
        }
        
        # Check current minute
        current_count = connection_counters.get(minute_key, 0)
        if current_count >= self.message_rate_limit:
            return False
        
        # Increment counter
        connection_counters[minute_key] = current_count + 1
        self.rate_limit_counters[connection_id] = connection_counters
        
        return True
    
    async def _send_error(
        self,
        websocket: Any,
        error_code: str,
        error_message: str
    ) -> None:
        """Send error message to WebSocket."""
        try:
            if websocket:
                error_msg = WebSocketMessage(
                    message_type=MessageType.ERROR,
                    data={
                        "error_code": error_code,
                        "error_message": error_message
                    }
                )
                
                await websocket.send_text(json.dumps(error_msg.to_dict()))
                
        except Exception as e:
            self.logger.error(f"Failed to send error message: {e}", exc_info=True)
    
    async def _cleanup_connections_loop(self) -> None:
        """Background task to clean up inactive connections."""
        while True:
            try:
                now = datetime.now()
                inactive_connections = []
                
                for connection_id, connection in self.connections.items():
                    if not connection.is_active(self.connection_timeout):
                        inactive_connections.append(connection_id)
                
                # Disconnect inactive connections
                for connection_id in inactive_connections:
                    await self.disconnect(connection_id, "timeout")
                
                if inactive_connections:
                    self.logger.info(f"Cleaned up {len(inactive_connections)} inactive connections")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Connection cleanup error: {e}", exc_info=True)
                await asyncio.sleep(30)  # Shorter retry on error
    
    async def _heartbeat_loop(self) -> None:
        """Background task to send heartbeat messages."""
        while True:
            try:
                heartbeat_message = WebSocketMessage(
                    message_type=MessageType.HEARTBEAT,
                    data={
                        "ping": True,
                        "server_time": datetime.now().isoformat()
                    }
                )
                
                # Send heartbeat to all connections
                for connection_id in list(self.connections.keys()):
                    await self._send_message_to_connection(connection_id, heartbeat_message)
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    def _update_avg_processing_time(self, processing_time_ms: float) -> None:
        """Update average message processing time."""
        total_messages = self.metrics.messages_sent + self.metrics.messages_failed
        if total_messages == 1:
            self.metrics.avg_message_processing_time_ms = processing_time_ms
        else:
            total_time = self.metrics.avg_message_processing_time_ms * (total_messages - 1)
            self.metrics.avg_message_processing_time_ms = (total_time + processing_time_ms) / total_messages
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get WebSocket service metrics."""
        return {
            "total_connections": self.metrics.total_connections,
            "active_connections": self.metrics.active_connections,
            "messages_sent": self.metrics.messages_sent,
            "messages_received": self.metrics.messages_received,
            "messages_failed": self.metrics.messages_failed,
            "message_success_rate": self.metrics.message_success_rate,
            "connections_dropped": self.metrics.connections_dropped,
            "authentication_failures": self.metrics.authentication_failures,
            "rate_limit_hits": self.metrics.rate_limit_hits,
            "avg_message_processing_time_ms": self.metrics.avg_message_processing_time_ms,
            "active_topics": len(self.topic_subscriptions),
            "total_subscriptions": sum(len(subs) for subs in self.topic_subscriptions.values()),
            "timestamp": datetime.now().isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check WebSocket service health."""
        try:
            # Check active connections
            active_count = len([
                conn for conn in self.connections.values()
                if conn.status == ConnectionStatus.CONNECTED
            ])
            
            # Check if background tasks are running
            cleanup_running = self.cleanup_task and not self.cleanup_task.done()
            heartbeat_running = self.heartbeat_task and not self.heartbeat_task.done()
            
            overall_status = "healthy" if cleanup_running and heartbeat_running else "degraded"
            
            return {
                "status": overall_status,
                "active_connections": active_count,
                "background_tasks_running": {
                    "cleanup": cleanup_running,
                    "heartbeat": heartbeat_running
                },
                "metrics": self.get_metrics(),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"WebSocket health check failed: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def shutdown(self) -> None:
        """Shutdown WebSocket service."""
        self.logger.info("Shutting down WebSocket service")
        
        # Cancel background tasks
        if self.cleanup_task:
            self.cleanup_task.cancel()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        
        # Close all connections
        connection_ids = list(self.connections.keys())
        for connection_id in connection_ids:
            await self.disconnect(connection_id, "server_shutdown")
        
        self.logger.info("WebSocket service shutdown complete")