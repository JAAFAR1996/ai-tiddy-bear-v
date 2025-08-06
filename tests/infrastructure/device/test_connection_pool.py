"""
Comprehensive tests for ESP32 connection pool.
Tests connection management, health checks, lifecycle, and concurrency.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from src.infrastructure.device.connection_pool import (
    ESP32ConnectionPool,
    ConnectionPool,  # Backward compatibility alias
    PooledConnection,
    ConnectionState,
    ConnectionMetrics
)


class MockConnection:
    """Mock connection for testing."""
    
    def __init__(self, device_id: str, healthy: bool = True):
        self.device_id = device_id
        self.healthy = healthy
        self.closed = False
        self.bytes_sent = 0
        self.bytes_received = 0
    
    async def send(self, data: bytes) -> int:
        if self.closed:
            raise ConnectionError("Connection closed")
        self.bytes_sent += len(data)
        return len(data)
    
    async def receive(self) -> bytes:
        if self.closed:
            raise ConnectionError("Connection closed")
        data = b"response"
        self.bytes_received += len(data)
        return data
    
    async def close(self):
        self.closed = True
    
    def is_healthy(self) -> bool:
        return self.healthy and not self.closed


class TestPooledConnection:
    """Test PooledConnection class."""
    
    def test_pooled_connection_creation(self):
        """Test creating a pooled connection."""
        mock_conn = MockConnection("device-1")
        pooled = PooledConnection(device_id="device-1", connection=mock_conn)
        
        assert pooled.device_id == "device-1"
        assert pooled.connection is mock_conn
        assert pooled.state == ConnectionState.CONNECTING
        assert isinstance(pooled.metrics, ConnectionMetrics)
        assert pooled.connection_id is not None
    
    def test_connection_expiration(self):
        """Test connection expiration logic."""
        mock_conn = MockConnection("device-1")
        pooled = PooledConnection(
            device_id="device-1", 
            connection=mock_conn,
            max_lifetime=timedelta(seconds=1)
        )
        
        # Should not be expired initially
        assert not pooled.is_expired()
        
        # Mock old creation time
        pooled.metrics.created_at = datetime.utcnow() - timedelta(seconds=2)
        assert pooled.is_expired()
    
    def test_idle_timeout(self):
        """Test idle timeout logic."""
        mock_conn = MockConnection("device-1")
        pooled = PooledConnection(
            device_id="device-1",
            connection=mock_conn,
            max_idle_time=timedelta(seconds=1)
        )
        
        # Should not be idle timeout initially
        assert not pooled.is_idle_timeout()
        
        # Mock old last used time
        pooled.metrics.last_used_at = datetime.utcnow() - timedelta(seconds=2)
        assert pooled.is_idle_timeout()
    
    def test_health_check_needed(self):
        """Test health check timing logic."""
        mock_conn = MockConnection("device-1")
        pooled = PooledConnection(
            device_id="device-1",
            connection=mock_conn,
            health_check_interval=timedelta(seconds=1)
        )
        
        # Should need health check initially
        assert pooled.needs_health_check()
        
        # After health check
        pooled.metrics.last_health_check = datetime.utcnow()
        assert not pooled.needs_health_check()
        
        # After interval passes
        pooled.metrics.last_health_check = datetime.utcnow() - timedelta(seconds=2)
        assert pooled.needs_health_check()
    
    def test_usage_metrics_update(self):
        """Test usage metrics updating."""
        mock_conn = MockConnection("device-1")
        pooled = PooledConnection(device_id="device-1", connection=mock_conn)
        
        initial_requests = pooled.metrics.total_requests
        initial_time = pooled.metrics.last_used_at
        
        pooled.update_usage(bytes_sent=100, bytes_received=50, response_time_ms=150.0)
        
        assert pooled.metrics.total_requests == initial_requests + 1
        assert pooled.metrics.bytes_sent == 100
        assert pooled.metrics.bytes_received == 50
        assert pooled.metrics.avg_response_time_ms == 150.0
        assert pooled.metrics.last_used_at > initial_time
    
    def test_failure_recording(self):
        """Test failure recording and error state transition."""
        mock_conn = MockConnection("device-1")
        pooled = PooledConnection(device_id="device-1", connection=mock_conn)
        pooled.state = ConnectionState.CONNECTED
        
        # Record a few failures
        for i in range(3):
            pooled.record_failure()
        
        assert pooled.metrics.failed_requests == 3
        assert pooled.state == ConnectionState.CONNECTED  # Not yet in error state
        
        # One more failure should trigger error state
        pooled.record_failure()
        assert pooled.state == ConnectionState.ERROR


class TestESP32ConnectionPool:
    """Test ESP32ConnectionPool class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.pool = ESP32ConnectionPool(
            max_connections=10,
            max_connections_per_device=2,
            health_check_interval=1,
            cleanup_interval=2
        )
    
    async def teardown_method(self):
        """Clean up after each test."""
        await self.pool.shutdown()
    
    def test_pool_initialization(self):
        """Test pool initialization."""
        assert self.pool.max_connections == 10
        assert self.pool.max_connections_per_device == 2
        assert len(self.pool._connections) == 0
        assert len(self.pool._connection_by_id) == 0
    
    def test_backward_compatibility_alias(self):
        """Test that ConnectionPool alias works."""
        pool = ConnectionPool(max_connections=5)
        assert isinstance(pool, ESP32ConnectionPool)
        assert pool.max_connections == 5
    
    @pytest.mark.asyncio
    async def test_add_connection_success(self):
        """Test successfully adding a connection."""
        mock_conn = MockConnection("device-1")
        
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        
        assert connection_id is not None
        assert len(self.pool._connections["device-1"]) == 1
        assert connection_id in self.pool._connection_by_id
        
        pooled = self.pool._connection_by_id[connection_id]
        assert pooled.device_id == "device-1"
        assert pooled.connection is mock_conn
        assert pooled.state == ConnectionState.CONNECTED
    
    @pytest.mark.asyncio
    async def test_add_connection_with_metadata(self):
        """Test adding connection with metadata."""
        mock_conn = MockConnection("device-1")
        metadata = {"version": "1.0", "type": "ESP32"}
        
        connection_id = await self.pool.add_connection("device-1", mock_conn, metadata)
        
        pooled = self.pool._connection_by_id[connection_id]
        assert pooled.metadata == metadata
    
    @pytest.mark.asyncio
    async def test_add_connection_pool_limit(self):
        """Test adding connection when pool limit is reached."""
        # Fill up the pool
        for i in range(self.pool.max_connections):
            mock_conn = MockConnection(f"device-{i}")
            await self.pool.add_connection(f"device-{i}", mock_conn)
        
        # Try to add one more
        mock_conn = MockConnection("device-overflow")
        with pytest.raises(ValueError, match="Pool limit exceeded"):
            await self.pool.add_connection("device-overflow", mock_conn)
    
    @pytest.mark.asyncio
    async def test_add_connection_device_limit(self):
        """Test adding connection when device limit is reached."""
        # Fill up connections for one device
        for i in range(self.pool.max_connections_per_device):
            mock_conn = MockConnection("device-1")
            await self.pool.add_connection("device-1", mock_conn)
        
        # Try to add one more for the same device
        mock_conn = MockConnection("device-1")
        with pytest.raises(ValueError, match="Device connection limit exceeded"):
            await self.pool.add_connection("device-1", mock_conn)
    
    @pytest.mark.asyncio
    async def test_get_connection_success(self):
        """Test successfully getting a connection."""
        mock_conn = MockConnection("device-1")
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        
        pooled = await self.pool.get_connection("device-1")
        
        assert pooled is not None
        assert pooled.connection_id == connection_id
        assert pooled.state == ConnectionState.BUSY
    
    @pytest.mark.asyncio
    async def test_get_connection_not_found(self):
        """Test getting connection for non-existent device."""
        pooled = await self.pool.get_connection("non-existent")
        assert pooled is None
    
    @pytest.mark.asyncio
    async def test_get_connection_load_balancing(self):
        """Test connection load balancing."""
        # Add two connections for the same device
        mock_conn1 = MockConnection("device-1")
        mock_conn2 = MockConnection("device-1")
        
        id1 = await self.pool.add_connection("device-1", mock_conn1)
        id2 = await self.pool.add_connection("device-1", mock_conn2)
        
        # Simulate usage on first connection
        pooled1 = self.pool._connection_by_id[id1]
        pooled1.metrics.total_requests = 10
        
        # Get connection should return the less used one
        pooled = await self.pool.get_connection("device-1")
        assert pooled.connection_id == id2
    
    @pytest.mark.asyncio
    async def test_release_connection_success(self):
        """Test successfully releasing a connection."""
        mock_conn = MockConnection("device-1")
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        
        # Get and then release the connection
        pooled = await self.pool.get_connection("device-1")
        await self.pool.release_connection(connection_id, success=True)
        
        assert pooled.state == ConnectionState.IDLE
    
    @pytest.mark.asyncio
    async def test_release_connection_failure(self):
        """Test releasing a connection after failure."""
        mock_conn = MockConnection("device-1")
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        
        # Get and then release with failure multiple times
        pooled = await self.pool.get_connection("device-1")
        
        for i in range(5):  # Enough failures to trigger error state
            await self.pool.release_connection(connection_id, success=False)
        
        # Connection should be removed from pool
        assert connection_id not in self.pool._connection_by_id
    
    @pytest.mark.asyncio
    async def test_remove_connection_specific(self):
        """Test removing a specific connection."""
        mock_conn = MockConnection("device-1")
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        
        await self.pool.remove_connection("device-1", connection_id)
        
        assert connection_id not in self.pool._connection_by_id
        assert len(self.pool._connections.get("device-1", [])) == 0
    
    @pytest.mark.asyncio
    async def test_remove_all_device_connections(self):
        """Test removing all connections for a device."""
        # Add multiple connections for the same device
        connections = []
        for i in range(2):
            mock_conn = MockConnection("device-1")
            connection_id = await self.pool.add_connection("device-1", mock_conn)
            connections.append(connection_id)
        
        await self.pool.remove_connection("device-1")
        
        for connection_id in connections:
            assert connection_id not in self.pool._connection_by_id
        assert "device-1" not in self.pool._connections
    
    @pytest.mark.asyncio
    async def test_connection_context_manager(self):
        """Test connection context manager."""
        mock_conn = MockConnection("device-1")
        await self.pool.add_connection("device-1", mock_conn)
        
        async with self.pool.get_connection_context("device-1") as connection:
            assert connection is not None
            assert connection.state == ConnectionState.BUSY
        
        # Connection should be released after context
        assert connection.state == ConnectionState.IDLE
    
    @pytest.mark.asyncio
    async def test_connection_context_manager_exception(self):
        """Test connection context manager with exception."""
        mock_conn = MockConnection("device-1")
        await self.pool.add_connection("device-1", mock_conn)
        
        with pytest.raises(ValueError):
            async with self.pool.get_connection_context("device-1") as connection:
                assert connection is not None
                raise ValueError("Test exception")
        
        # Connection should still be released (but marked as failed)
        assert connection.metrics.failed_requests > 0
    
    @pytest.mark.asyncio
    async def test_health_check_function_setup(self):
        """Test setting up health check function."""
        async def mock_health_check(conn):
            return conn.is_healthy()
        
        self.pool.set_health_check_function(mock_health_check)
        assert self.pool._health_check_func is mock_health_check
    
    @pytest.mark.asyncio
    async def test_health_check_connection_healthy(self):
        """Test health check on healthy connection."""
        async def mock_health_check(conn):
            return True
        
        self.pool.set_health_check_function(mock_health_check)
        
        mock_conn = MockConnection("device-1")
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        
        is_healthy = await self.pool.health_check_connection(connection_id)
        
        assert is_healthy is True
        pooled = self.pool._connection_by_id[connection_id]
        assert pooled.metrics.last_health_check is not None
        assert pooled.metrics.health_check_failures == 0
    
    @pytest.mark.asyncio
    async def test_health_check_connection_unhealthy(self):
        """Test health check on unhealthy connection."""
        async def mock_health_check(conn):
            return False
        
        self.pool.set_health_check_function(mock_health_check)
        
        mock_conn = MockConnection("device-1")
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        
        # Multiple failed health checks should mark as error
        for i in range(3):
            is_healthy = await self.pool.health_check_connection(connection_id)
            assert is_healthy is False
        
        pooled = self.pool._connection_by_id[connection_id]
        assert pooled.state == ConnectionState.ERROR
        assert pooled.metrics.health_check_failures >= 3
    
    @pytest.mark.asyncio
    async def test_health_check_connection_exception(self):
        """Test health check with exception."""
        async def mock_health_check(conn):
            raise Exception("Health check failed")
        
        self.pool.set_health_check_function(mock_health_check)
        
        mock_conn = MockConnection("device-1")
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        
        is_healthy = await self.pool.health_check_connection(connection_id)
        
        assert is_healthy is False
        pooled = self.pool._connection_by_id[connection_id]
        assert pooled.state == ConnectionState.ERROR
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_connections(self):
        """Test cleanup of expired connections."""
        mock_conn = MockConnection("device-1")
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        
        # Make connection expired
        pooled = self.pool._connection_by_id[connection_id]
        pooled.metrics.created_at = datetime.utcnow() - timedelta(hours=2)
        
        cleaned_count = await self.pool.cleanup_expired_connections()
        
        assert cleaned_count == 1
        assert connection_id not in self.pool._connection_by_id
    
    @pytest.mark.asyncio
    async def test_cleanup_idle_connections(self):
        """Test cleanup of idle connections."""
        mock_conn = MockConnection("device-1")
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        
        # Make connection idle timeout
        pooled = self.pool._connection_by_id[connection_id]
        pooled.metrics.last_used_at = datetime.utcnow() - timedelta(hours=1)
        
        cleaned_count = await self.pool.cleanup_expired_connections()
        
        assert cleaned_count == 1
        assert connection_id not in self.pool._connection_by_id
    
    @pytest.mark.asyncio
    async def test_cleanup_error_connections(self):
        """Test cleanup of error connections."""
        mock_conn = MockConnection("device-1")
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        
        # Mark connection as error
        pooled = self.pool._connection_by_id[connection_id]
        pooled.state = ConnectionState.ERROR
        
        cleaned_count = await self.pool.cleanup_expired_connections()
        
        assert cleaned_count == 1
        assert connection_id not in self.pool._connection_by_id
    
    @pytest.mark.asyncio
    async def test_pool_statistics(self):
        """Test pool statistics collection."""
        # Add some connections
        for i in range(3):
            mock_conn = MockConnection(f"device-{i}")
            await self.pool.add_connection(f"device-{i}", mock_conn)
        
        stats = await self.pool.get_pool_statistics()
        
        assert stats['total_connections'] == 3
        assert stats['active_connections'] == 3
        assert stats['device_count'] == 3
        assert stats['connection_creates'] == 3
        assert 'connection_utilization' in stats
    
    @pytest.mark.asyncio
    async def test_device_connections_info(self):
        """Test getting device connection information."""
        mock_conn = MockConnection("device-1")
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        
        connections_info = await self.pool.get_device_connections("device-1")
        
        assert len(connections_info) == 1
        conn_info = connections_info[0]
        assert conn_info['connection_id'] == connection_id
        assert conn_info['state'] == ConnectionState.CONNECTED.value
        assert 'created_at' in conn_info
        assert 'total_requests' in conn_info
    
    @pytest.mark.asyncio
    async def test_background_tasks(self):
        """Test background task management."""
        await self.pool.start_background_tasks()
        
        assert self.pool._cleanup_task is not None
        assert self.pool._health_check_task is not None
        assert not self.pool._cleanup_task.done()
        assert not self.pool._health_check_task.done()
        
        await self.pool.stop_background_tasks()
        
        assert self.pool._cleanup_task is None
        assert self.pool._health_check_task is None
    
    @pytest.mark.asyncio
    async def test_connection_factory(self):
        """Test connection factory setup."""
        async def mock_factory(device_id):
            return MockConnection(device_id)
        
        self.pool.set_connection_factory(mock_factory)
        assert self.pool._connection_factory is mock_factory
    
    @pytest.mark.asyncio
    async def test_cleanup_function(self):
        """Test cleanup function setup and usage."""
        cleanup_called = []
        
        async def mock_cleanup(conn):
            cleanup_called.append(conn)
            await conn.close()
        
        self.pool.set_cleanup_function(mock_cleanup)
        
        # Add and remove a connection
        mock_conn = MockConnection("device-1")
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        await self.pool.remove_connection("device-1", connection_id)
        
        assert len(cleanup_called) == 1
        assert cleanup_called[0] is mock_conn
        assert mock_conn.closed
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown(self):
        """Test graceful pool shutdown."""
        # Add some connections
        connections = []
        for i in range(3):
            mock_conn = MockConnection(f"device-{i}")
            connection_id = await self.pool.add_connection(f"device-{i}", mock_conn)
            connections.append((connection_id, mock_conn))
        
        # Start background tasks
        await self.pool.start_background_tasks()
        
        # Shutdown should clean everything up
        await self.pool.shutdown()
        
        # All connections should be removed
        assert len(self.pool._connection_by_id) == 0
        assert len(self.pool._connections) == 0
        
        # Tasks should be stopped
        assert self.pool._cleanup_task is None
        assert self.pool._health_check_task is None


class TestConcurrency:
    """Test concurrent access to connection pool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.pool = ESP32ConnectionPool(max_connections=50, max_connections_per_device=10)
    
    async def teardown_method(self):
        """Clean up after each test."""
        await self.pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_concurrent_add_connections(self):
        """Test concurrent connection additions."""
        async def add_connection(device_id):
            mock_conn = MockConnection(device_id)
            return await self.pool.add_connection(device_id, mock_conn)
        
        # Add connections concurrently
        tasks = [add_connection(f"device-{i}") for i in range(20)]
        connection_ids = await asyncio.gather(*tasks)
        
        # All connections should be added successfully
        assert len(connection_ids) == 20
        assert len(set(connection_ids)) == 20  # All unique
        assert len(self.pool._connection_by_id) == 20
    
    @pytest.mark.asyncio
    async def test_concurrent_get_and_release(self):
        """Test concurrent get and release operations."""
        # Add some connections first
        device_ids = [f"device-{i}" for i in range(5)]
        for device_id in device_ids:
            mock_conn = MockConnection(device_id)
            await self.pool.add_connection(device_id, mock_conn)
        
        results = []
        
        async def get_and_release(device_id):
            async with self.pool.get_connection_context(device_id) as conn:
                if conn:
                    results.append(conn.device_id)
                    await asyncio.sleep(0.01)  # Simulate work
        
        # Run concurrent operations
        tasks = [get_and_release(f"device-{i % 5}") for i in range(20)]
        await asyncio.gather(*tasks)
        
        # All operations should complete successfully
        assert len(results) == 20
    
    @pytest.mark.asyncio
    async def test_concurrent_cleanup(self):
        """Test concurrent cleanup operations."""
        # Add many connections
        for i in range(10):
            mock_conn = MockConnection(f"device-{i}")
            await self.pool.add_connection(f"device-{i}", mock_conn)
        
        # Run cleanup concurrently with other operations
        cleanup_task = asyncio.create_task(self.pool.cleanup_expired_connections())
        
        async def use_connection(device_id):
            async with self.pool.get_connection_context(device_id) as conn:
                if conn:
                    await asyncio.sleep(0.01)
        
        use_tasks = [use_connection(f"device-{i}") for i in range(10)]
        
        # Wait for all tasks
        await asyncio.gather(cleanup_task, *use_tasks, return_exceptions=True)
        
        # Pool should still be in consistent state
        stats = await self.pool.get_pool_statistics()
        assert isinstance(stats, dict)


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.pool = ESP32ConnectionPool(max_connections=2, max_connections_per_device=1)
    
    async def teardown_method(self):
        """Clean up after each test."""
        await self.pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_health_check_without_function(self):
        """Test health check when no function is configured."""
        mock_conn = MockConnection("device-1")
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        
        # Should return True when no health check function is set
        is_healthy = await self.pool.health_check_connection(connection_id)
        assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_health_check_nonexistent_connection(self):
        """Test health check on non-existent connection."""
        is_healthy = await self.pool.health_check_connection("non-existent")
        assert is_healthy is False
    
    @pytest.mark.asyncio
    async def test_release_nonexistent_connection(self):
        """Test releasing non-existent connection."""
        # Should not raise an exception
        await self.pool.release_connection("non-existent")
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent_connection(self):
        """Test removing non-existent connection."""
        # Should not raise an exception
        await self.pool.remove_connection("non-existent", "non-existent")
    
    @pytest.mark.asyncio
    async def test_get_device_connections_empty(self):
        """Test getting connections for device with no connections."""
        connections = await self.pool.get_device_connections("non-existent")
        assert connections == []
    
    @pytest.mark.asyncio
    async def test_cleanup_function_exception(self):
        """Test cleanup function that raises exception."""
        async def failing_cleanup(conn):
            raise Exception("Cleanup failed")
        
        self.pool.set_cleanup_function(failing_cleanup)
        
        mock_conn = MockConnection("device-1")
        connection_id = await self.pool.add_connection("device-1", mock_conn)
        
        # Should handle exception gracefully
        await self.pool.remove_connection("device-1", connection_id)
        
        # Connection should still be removed
        assert connection_id not in self.pool._connection_by_id
    
    @pytest.mark.asyncio
    async def test_background_task_exception_handling(self):
        """Test that background tasks handle exceptions gracefully."""
        # Mock cleanup to raise exception
        original_cleanup = self.pool.cleanup_expired_connections
        
        async def failing_cleanup():
            raise Exception("Cleanup failed")
        
        self.pool.cleanup_expired_connections = failing_cleanup
        
        # Start background tasks
        await self.pool.start_background_tasks()
        
        # Wait a bit for tasks to run
        await asyncio.sleep(0.1)
        
        # Tasks should still be running (not crashed)
        assert not self.pool._cleanup_task.done()
        
        # Restore original method
        self.pool.cleanup_expired_connections = original_cleanup