"""
🧸 AI TEDDY BEAR V5 - ESP32 CONNECTION POOL
==========================================
Professional connection pool for ESP32 devices with:
- Connection lifecycle management (create, validate, cleanup)
- Health checking and automatic recovery
- Thread-safe operations with proper locking
- Connection pooling with size limits and timeouts
- Comprehensive error handling and logging
- Metrics and monitoring capabilities
"""

import asyncio
import logging
import threading
import time
import weakref
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, Set, Any, Callable, List
from contextlib import asynccontextmanager
import uuid


logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state enumeration."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    IDLE = "idle"
    BUSY = "busy"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    EXPIRED = "expired"


@dataclass
class ConnectionMetrics:
    """Connection metrics and statistics."""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used_at: datetime = field(default_factory=datetime.utcnow)
    last_health_check: Optional[datetime] = None
    total_requests: int = 0
    failed_requests: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    avg_response_time_ms: float = 0.0
    health_check_failures: int = 0
    reconnection_count: int = 0


@dataclass
class PooledConnection:
    """Wrapper for pooled connections with metadata."""
    device_id: str
    connection: Any
    state: ConnectionState = ConnectionState.CONNECTING
    metrics: ConnectionMetrics = field(default_factory=ConnectionMetrics)
    connection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    max_idle_time: timedelta = field(default=timedelta(minutes=5))
    max_lifetime: timedelta = field(default=timedelta(hours=1))
    health_check_interval: timedelta = field(default=timedelta(minutes=1))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if connection has exceeded its maximum lifetime."""
        return datetime.utcnow() - self.metrics.created_at > self.max_lifetime
    
    def is_idle_timeout(self) -> bool:
        """Check if connection has been idle too long."""
        return datetime.utcnow() - self.metrics.last_used_at > self.max_idle_time
    
    def needs_health_check(self) -> bool:
        """Check if connection needs a health check."""
        if self.metrics.last_health_check is None:
            return True
        return datetime.utcnow() - self.metrics.last_health_check > self.health_check_interval
    
    def update_usage(self, bytes_sent: int = 0, bytes_received: int = 0, response_time_ms: float = 0.0):
        """Update connection usage metrics."""
        self.metrics.last_used_at = datetime.utcnow()
        self.metrics.total_requests += 1
        self.metrics.bytes_sent += bytes_sent
        self.metrics.bytes_received += bytes_received
        
        # Update average response time
        if response_time_ms > 0:
            if self.metrics.avg_response_time_ms == 0:
                self.metrics.avg_response_time_ms = response_time_ms
            else:
                self.metrics.avg_response_time_ms = (
                    self.metrics.avg_response_time_ms * 0.9 + response_time_ms * 0.1
                )
    
    def record_failure(self):
        """Record a failed request."""
        self.metrics.failed_requests += 1
        if self.metrics.failed_requests > 3:  # Too many failures
            self.state = ConnectionState.ERROR


class ESP32ConnectionPool:
    """
    Professional connection pool for ESP32 devices with comprehensive management.
    
    Features:
    - Thread-safe connection management
    - Health checking and automatic recovery
    - Connection lifecycle management
    - Pooling with size limits and timeouts
    - Metrics and monitoring
    """
    
    def __init__(
        self,
        max_connections: int = 100,
        max_connections_per_device: int = 3,
        connection_timeout: float = 30.0,
        health_check_interval: int = 60,
        cleanup_interval: int = 300,
        enable_metrics: bool = True
    ):
        """
        Initialize the connection pool.
        
        Args:
            max_connections: Maximum total connections in pool
            max_connections_per_device: Maximum connections per device
            connection_timeout: Connection timeout in seconds
            health_check_interval: Health check interval in seconds
            cleanup_interval: Cleanup interval in seconds
            enable_metrics: Whether to collect metrics
        """
        self.max_connections = max_connections
        self.max_connections_per_device = max_connections_per_device
        self.connection_timeout = connection_timeout
        self.health_check_interval = timedelta(seconds=health_check_interval)
        self.cleanup_interval = cleanup_interval
        self.enable_metrics = enable_metrics
        
        # Thread-safe connection storage
        self._connections: Dict[str, List[PooledConnection]] = {}
        self._connection_by_id: Dict[str, PooledConnection] = {}
        self._lock = threading.RLock()
        
        # Pool statistics
        self._pool_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'idle_connections': 0,
            'failed_connections': 0,
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'connection_creates': 0,
            'connection_destroys': 0,
            'health_checks': 0,
            'health_check_failures': 0
        }
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Connection factory and health check functions
        self._connection_factory: Optional[Callable] = None
        self._health_check_func: Optional[Callable] = None
        self._cleanup_func: Optional[Callable] = None
        
        logger.info(
            f"ESP32ConnectionPool initialized: max_connections={max_connections}, "
            f"max_per_device={max_connections_per_device}"
        )
    
    def set_connection_factory(self, factory: Callable):
        """Set the factory function for creating connections."""
        self._connection_factory = factory
    
    def set_health_check_function(self, health_check: Callable):
        """Set the function for checking connection health."""
        self._health_check_func = health_check
    
    def set_cleanup_function(self, cleanup: Callable):
        """Set the function for cleaning up connections."""
        self._cleanup_func = cleanup
    
    async def start_background_tasks(self):
        """Start background maintenance tasks."""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        if not self._health_check_task:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info("Background tasks started")
    
    async def stop_background_tasks(self):
        """Stop background maintenance tasks."""
        self._shutdown_event.set()
        
        tasks_to_cancel = [
            task for task in [self._cleanup_task, self._health_check_task]
            if task and not task.done()
        ]
        
        if tasks_to_cancel:
            for task in tasks_to_cancel:
                task.cancel()
            
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        
        self._cleanup_task = None
        self._health_check_task = None
        
        logger.info("Background tasks stopped")
    
    async def add_connection(
        self, 
        device_id: str, 
        connection: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a connection to the pool.
        
        Args:
            device_id: Unique device identifier
            connection: The actual connection object
            metadata: Optional metadata for the connection
            
        Returns:
            Connection ID for tracking
            
        Raises:
            ValueError: If pool limits are exceeded
        """
        async with self._async_lock():
            try:
                # Check pool limits
                if len(self._connection_by_id) >= self.max_connections:
                    raise ValueError(f"Pool limit exceeded: {self.max_connections}")
                
                device_connections = self._connections.get(device_id, [])
                if len(device_connections) >= self.max_connections_per_device:
                    raise ValueError(
                        f"Device connection limit exceeded: {self.max_connections_per_device}"
                    )
                
                # Create pooled connection
                pooled_conn = PooledConnection(
                    device_id=device_id,
                    connection=connection,
                    state=ConnectionState.CONNECTED,
                    metadata=metadata or {}
                )
                
                # Add to pool
                if device_id not in self._connections:
                    self._connections[device_id] = []
                
                self._connections[device_id].append(pooled_conn)
                self._connection_by_id[pooled_conn.connection_id] = pooled_conn
                
                # Update statistics
                self._pool_stats['total_connections'] += 1
                self._pool_stats['active_connections'] += 1
                self._pool_stats['connection_creates'] += 1
                
                logger.info(
                    f"Added connection for device {device_id}: {pooled_conn.connection_id}"
                )
                
                return pooled_conn.connection_id
                
            except Exception as e:
                logger.error(f"Error adding connection for device {device_id}: {e}")
                self._pool_stats['failed_connections'] += 1
                raise
    
    async def get_connection(self, device_id: str) -> Optional[PooledConnection]:
        """
        Get an available connection for a device.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Available pooled connection or None
        """
        async with self._async_lock():
            device_connections = self._connections.get(device_id, [])
            
            # Find best available connection
            best_connection = None
            for conn in device_connections:
                if conn.state in [ConnectionState.CONNECTED, ConnectionState.IDLE]:
                    if not conn.is_expired() and not conn.is_idle_timeout():
                        if best_connection is None or conn.metrics.total_requests < best_connection.metrics.total_requests:
                            best_connection = conn
            
            if best_connection:
                best_connection.state = ConnectionState.BUSY
                best_connection.metrics.last_used_at = datetime.utcnow()
                
                logger.debug(f"Retrieved connection for device {device_id}: {best_connection.connection_id}")
                return best_connection
            
            logger.debug(f"No available connection for device {device_id}")
            return None
    
    async def release_connection(self, connection_id: str, success: bool = True):
        """
        Release a connection back to the pool.
        
        Args:
            connection_id: Connection ID to release
            success: Whether the operation was successful
        """
        async with self._async_lock():
            conn = self._connection_by_id.get(connection_id)
            if not conn:
                logger.warning(f"Connection not found for release: {connection_id}")
                return
            
            if success:
                conn.state = ConnectionState.IDLE
                self._pool_stats['successful_requests'] += 1
            else:
                conn.record_failure()
                self._pool_stats['failed_requests'] += 1
                
                if conn.state == ConnectionState.ERROR:
                    await self._remove_connection_internal(connection_id)
                    return
            
            self._pool_stats['total_requests'] += 1
            logger.debug(f"Released connection: {connection_id}")
    
    async def remove_connection(self, device_id: str, connection_id: Optional[str] = None):
        """
        Remove connection(s) from the pool.
        
        Args:
            device_id: Device identifier
            connection_id: Specific connection ID (optional)
        """
        async with self._async_lock():
            if connection_id:
                await self._remove_connection_internal(connection_id)
            else:
                # Remove all connections for device
                device_connections = self._connections.get(device_id, []).copy()
                for conn in device_connections:
                    await self._remove_connection_internal(conn.connection_id)
    
    async def _remove_connection_internal(self, connection_id: str):
        """Internal method to remove a connection."""
        conn = self._connection_by_id.get(connection_id)
        if not conn:
            return
        
        try:
            # Cleanup connection if function provided
            if self._cleanup_func:
                await self._cleanup_func(conn.connection)
        except Exception as e:
            logger.error(f"Error cleaning up connection {connection_id}: {e}")
        
        # Remove from pool
        device_connections = self._connections.get(conn.device_id, [])
        device_connections[:] = [c for c in device_connections if c.connection_id != connection_id]
        
        if not device_connections:
            self._connections.pop(conn.device_id, None)
        
        self._connection_by_id.pop(connection_id, None)
        
        # Update statistics
        self._pool_stats['active_connections'] = max(0, self._pool_stats['active_connections'] - 1)
        self._pool_stats['connection_destroys'] += 1
        
        logger.info(f"Removed connection: {connection_id}")
    
    @asynccontextmanager
    async def get_connection_context(self, device_id: str):
        """
        Context manager for getting and automatically releasing connections.
        
        Args:
            device_id: Device identifier
            
        Yields:
            PooledConnection or None
        """
        connection = await self.get_connection(device_id)
        success = False
        
        try:
            yield connection
            success = True
        except Exception as e:
            logger.error(f"Error in connection context for device {device_id}: {e}")
            raise
        finally:
            if connection:
                await self.release_connection(connection.connection_id, success)
    
    async def health_check_connection(self, connection_id: str) -> bool:
        """
        Perform health check on a specific connection.
        
        Args:
            connection_id: Connection ID to check
            
        Returns:
            True if connection is healthy
        """
        conn = self._connection_by_id.get(connection_id)
        if not conn:
            return False
        
        if not self._health_check_func:
            logger.warning("No health check function configured")
            return True
        
        try:
            is_healthy = await self._health_check_func(conn.connection)
            conn.metrics.last_health_check = datetime.utcnow()
            
            if is_healthy:
                if conn.state == ConnectionState.ERROR:
                    conn.state = ConnectionState.IDLE  # Recover from error
                conn.metrics.health_check_failures = 0
            else:
                conn.metrics.health_check_failures += 1
                if conn.metrics.health_check_failures >= 3:
                    conn.state = ConnectionState.ERROR
            
            self._pool_stats['health_checks'] += 1
            if not is_healthy:
                self._pool_stats['health_check_failures'] += 1
            
            return is_healthy
            
        except Exception as e:
            logger.error(f"Health check failed for connection {connection_id}: {e}")
            conn.metrics.health_check_failures += 1
            conn.state = ConnectionState.ERROR
            self._pool_stats['health_check_failures'] += 1
            return False
    
    async def get_pool_statistics(self) -> Dict[str, Any]:
        """Get comprehensive pool statistics."""
        async with self._async_lock():
            # Update real-time statistics
            active_count = sum(
                1 for conn in self._connection_by_id.values()
                if conn.state in [ConnectionState.CONNECTED, ConnectionState.BUSY]
            )
            idle_count = sum(
                1 for conn in self._connection_by_id.values()
                if conn.state == ConnectionState.IDLE
            )
            error_count = sum(
                1 for conn in self._connection_by_id.values()
                if conn.state == ConnectionState.ERROR
            )
            
            self._pool_stats.update({
                'active_connections': active_count,
                'idle_connections': idle_count,
                'error_connections': error_count,
                'device_count': len(self._connections),
                'connection_utilization': active_count / max(1, self.max_connections) * 100
            })
            
            return self._pool_stats.copy()
    
    async def get_device_connections(self, device_id: str) -> List[Dict[str, Any]]:
        """Get information about connections for a specific device."""
        async with self._async_lock():
            device_connections = self._connections.get(device_id, [])
            
            return [
                {
                    'connection_id': conn.connection_id,
                    'state': conn.state.value,
                    'created_at': conn.metrics.created_at.isoformat(),
                    'last_used_at': conn.metrics.last_used_at.isoformat(),
                    'total_requests': conn.metrics.total_requests,
                    'failed_requests': conn.metrics.failed_requests,
                    'avg_response_time_ms': conn.metrics.avg_response_time_ms,
                    'is_expired': conn.is_expired(),
                    'needs_health_check': conn.needs_health_check()
                }
                for conn in device_connections
            ]
    
    async def cleanup_expired_connections(self) -> int:
        """Clean up expired and unhealthy connections."""
        async with self._async_lock():
            expired_connections = []
            
            for conn in self._connection_by_id.values():
                if (conn.is_expired() or 
                    conn.is_idle_timeout() or 
                    conn.state == ConnectionState.ERROR):
                    expired_connections.append(conn.connection_id)
            
            for connection_id in expired_connections:
                await self._remove_connection_internal(connection_id)
            
            if expired_connections:
                logger.info(f"Cleaned up {len(expired_connections)} expired connections")
            
            return len(expired_connections)
    
    async def _cleanup_loop(self):
        """Background cleanup loop."""
        while not self._shutdown_event.is_set():
            try:
                await self.cleanup_expired_connections()
                await asyncio.wait_for(
                    self._shutdown_event.wait(), 
                    timeout=self.cleanup_interval
                )
            except asyncio.TimeoutError:
                continue  # Normal timeout, continue loop
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _health_check_loop(self):
        """Background health check loop."""
        while not self._shutdown_event.is_set():
            try:
                async with self._async_lock():
                    connections_to_check = [
                        conn for conn in self._connection_by_id.values()
                        if conn.needs_health_check() and conn.state != ConnectionState.ERROR
                    ]
                
                # Perform health checks without holding the lock
                for conn in connections_to_check:
                    try:
                        await self.health_check_connection(conn.connection_id)
                    except Exception as e:
                        logger.error(f"Health check error for {conn.connection_id}: {e}")
                
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.health_check_interval.total_seconds()
                )
            except asyncio.TimeoutError:
                continue  # Normal timeout, continue loop
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    @asynccontextmanager
    async def _async_lock(self):
        """Async context manager for thread lock."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._lock.acquire)
        try:
            yield
        finally:
            self._lock.release()
    
    async def shutdown(self):
        """Gracefully shutdown the connection pool."""
        logger.info("Shutting down connection pool...")
        
        # Stop background tasks
        await self.stop_background_tasks()
        
        # Close all connections
        async with self._async_lock():
            connection_ids = list(self._connection_by_id.keys())
            for connection_id in connection_ids:
                await self._remove_connection_internal(connection_id)
        
        logger.info("Connection pool shutdown complete")


# Backward compatibility alias
ConnectionPool = ESP32ConnectionPool
