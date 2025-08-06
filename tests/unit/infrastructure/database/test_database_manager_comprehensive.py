"""
Comprehensive unit tests for database_manager module.
Production-grade database management testing with high availability and failover.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from src.infrastructure.database.database_manager import (
    DatabaseManager,
    DatabaseNode,
    DatabaseConfig,
    RetryConfig,
    CircuitBreakerConfig,
    CircuitBreaker,
    ConnectionMetrics,
    DatabaseConnectionState,
    DatabaseRole,
    RetryStrategy,
    get_database_manager,
    execute_query,
    fetch_one,
    fetch_all,
    execute_command,
    get_connection,
    initialize_database,
    close_database
)


class TestDatabaseConfig:
    """Test DatabaseConfig dataclass."""

    def test_default_configuration(self):
        """Test default database configuration values."""
        config = DatabaseConfig(url="postgresql://test")
        
        assert config.url == "postgresql://test"
        assert config.role == DatabaseRole.PRIMARY
        assert config.max_connections == 20
        assert config.min_connections == 5
        assert config.max_idle_time == 300.0
        assert config.max_lifetime == 3600.0
        assert config.acquire_timeout == 30.0
        assert config.query_timeout == 60.0
        assert config.command_timeout == 300.0
        assert config.ssl_mode == "require"
        assert config.application_name == "ai-teddy-bear"

    def test_custom_configuration(self):
        """Test custom database configuration."""
        config = DatabaseConfig(
            url="postgresql://custom",
            role=DatabaseRole.REPLICA,
            max_connections=50,
            min_connections=10,
            application_name="custom-app"
        )
        
        assert config.url == "postgresql://custom"
        assert config.role == DatabaseRole.REPLICA
        assert config.max_connections == 50
        assert config.min_connections == 10
        assert config.application_name == "custom-app"


class TestRetryConfig:
    """Test RetryConfig dataclass."""

    def test_default_retry_configuration(self):
        """Test default retry configuration values."""
        config = RetryConfig()
        
        assert config.max_attempts == 3
        assert config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.jitter is True
        assert config.backoff_multiplier == 2.0

    def test_custom_retry_configuration(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            strategy=RetryStrategy.LINEAR_BACKOFF,
            base_delay=2.0,
            max_delay=120.0,
            jitter=False
        )
        
        assert config.max_attempts == 5
        assert config.strategy == RetryStrategy.LINEAR_BACKOFF
        assert config.base_delay == 2.0
        assert config.max_delay == 120.0
        assert config.jitter is False


class TestCircuitBreaker:
    """Test CircuitBreaker functionality."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker for testing."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=10.0
        )
        return CircuitBreaker(config)

    def test_initial_state_closed(self, circuit_breaker):
        """Test circuit breaker starts in CLOSED state."""
        assert circuit_breaker.state == "CLOSED"
        assert circuit_breaker.can_execute() is True
        assert circuit_breaker.failure_count == 0

    def test_failure_threshold_opens_circuit(self, circuit_breaker):
        """Test circuit opens after failure threshold."""
        # Record failures up to threshold
        for _ in range(3):
            circuit_breaker.record_failure()
            
        assert circuit_breaker.state == "OPEN"
        assert circuit_breaker.can_execute() is False

    def test_timeout_transitions_to_half_open(self, circuit_breaker):
        """Test circuit transitions to HALF_OPEN after timeout."""
        # Open the circuit
        for _ in range(3):
            circuit_breaker.record_failure()
        assert circuit_breaker.state == "OPEN"
        
        # Simulate timeout by setting old failure time
        circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=15)
        
        assert circuit_breaker.can_execute() is True
        assert circuit_breaker.state == "HALF_OPEN"

    def test_half_open_success_closes_circuit(self, circuit_breaker):
        """Test successful operations in HALF_OPEN close circuit."""
        # Open circuit and transition to HALF_OPEN
        for _ in range(3):
            circuit_breaker.record_failure()
        circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=15)
        circuit_breaker.can_execute()  # Transition to HALF_OPEN
        
        # Record successful operations
        for _ in range(2):
            circuit_breaker.record_success()
            
        assert circuit_breaker.state == "CLOSED"
        assert circuit_breaker.failure_count == 0

    def test_half_open_failure_reopens_circuit(self, circuit_breaker):
        """Test failure in HALF_OPEN reopens circuit."""
        # Open circuit and transition to HALF_OPEN
        for _ in range(3):
            circuit_breaker.record_failure()
        circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=15)
        circuit_breaker.can_execute()  # Transition to HALF_OPEN
        
        # Record failure
        circuit_breaker.record_failure()
        
        assert circuit_breaker.state == "OPEN"

    def test_half_open_max_calls_limit(self, circuit_breaker):
        """Test HALF_OPEN respects max calls limit."""
        # Open circuit and transition to HALF_OPEN
        for _ in range(3):
            circuit_breaker.record_failure()
        circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=15)
        circuit_breaker.can_execute()  # Transition to HALF_OPEN
        
        # Exceed max calls
        circuit_breaker.success_count = 3  # Set to max
        assert circuit_breaker.can_execute() is False


class TestDatabaseNode:
    """Test DatabaseNode functionality."""

    @pytest.fixture
    def db_config(self):
        """Create database configuration for testing."""
        return DatabaseConfig(
            url="postgresql://test:test@localhost/test",
            role=DatabaseRole.PRIMARY,
            max_connections=10,
            min_connections=2
        )

    @pytest.fixture
    def retry_config(self):
        """Create retry configuration for testing."""
        return RetryConfig(max_attempts=2, base_delay=0.1)

    @pytest.fixture
    def database_node(self, db_config, retry_config):
        """Create database node for testing."""
        return DatabaseNode(db_config, retry_config)

    def test_node_initialization(self, database_node):
        """Test database node initialization."""
        assert database_node.config.role == DatabaseRole.PRIMARY
        assert database_node.state == DatabaseConnectionState.HEALTHY
        assert database_node.pool is None
        assert isinstance(database_node.metrics, ConnectionMetrics)
        assert isinstance(database_node.circuit_breaker, CircuitBreaker)

    @pytest.mark.asyncio
    async def test_initialize_success(self, database_node):
        """Test successful node initialization."""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock()
        mock_conn.execute = AsyncMock()

        with patch('asyncpg.create_pool', return_value=mock_pool):
            await database_node.initialize()
            
        assert database_node.pool == mock_pool
        assert database_node.state == DatabaseConnectionState.HEALTHY
        assert database_node.metrics.last_success_time is not None

    @pytest.mark.asyncio
    async def test_initialize_failure(self, database_node):
        """Test node initialization failure."""
        with patch('asyncpg.create_pool', side_effect=Exception("Connection failed")):
            with pytest.raises(Exception, match="Connection failed"):
                await database_node.initialize()
                
        assert database_node.state == DatabaseConnectionState.FAILED
        assert database_node.metrics.last_failure_time is not None

    @pytest.mark.asyncio
    async def test_close_node(self, database_node):
        """Test node closure."""
        mock_pool = AsyncMock()
        database_node.pool = mock_pool
        
        await database_node.close()
        
        mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_connection_success(self, database_node):
        """Test successful connection acquisition."""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        database_node.pool = mock_pool
        database_node.circuit_breaker = Mock()
        database_node.circuit_breaker.can_execute.return_value = True
        
        mock_pool.acquire.return_value = mock_conn
        mock_pool.release = AsyncMock()
        
        async with database_node.acquire_connection() as conn:
            assert conn == mock_conn
            assert database_node.metrics.active_connections == 1
            
        mock_pool.release.assert_called_once_with(mock_conn)
        assert database_node.metrics.active_connections == 0

    @pytest.mark.asyncio
    async def test_acquire_connection_circuit_breaker_open(self, database_node):
        """Test connection acquisition with circuit breaker open."""
        database_node.circuit_breaker = Mock()
        database_node.circuit_breaker.can_execute.return_value = False
        
        with pytest.raises(ConnectionError, match="Circuit breaker is open"):
            async with database_node.acquire_connection():
                pass

    @pytest.mark.asyncio
    async def test_acquire_connection_no_pool(self, database_node):
        """Test connection acquisition without initialized pool."""
        database_node.pool = None
        database_node.circuit_breaker = Mock()
        database_node.circuit_breaker.can_execute.return_value = True
        
        with pytest.raises(ConnectionError, match="Database pool not initialized"):
            async with database_node.acquire_connection():
                pass

    def test_calculate_retry_delay_exponential(self, database_node):
        """Test exponential backoff retry delay calculation."""
        database_node.retry_config.strategy = RetryStrategy.EXPONENTIAL_BACKOFF
        database_node.retry_config.base_delay = 1.0
        database_node.retry_config.backoff_multiplier = 2.0
        database_node.retry_config.jitter = False
        
        assert database_node._calculate_retry_delay(0) == 1.0
        assert database_node._calculate_retry_delay(1) == 2.0
        assert database_node._calculate_retry_delay(2) == 4.0

    def test_calculate_retry_delay_linear(self, database_node):
        """Test linear backoff retry delay calculation."""
        database_node.retry_config.strategy = RetryStrategy.LINEAR_BACKOFF
        database_node.retry_config.base_delay = 1.0
        database_node.retry_config.jitter = False
        
        assert database_node._calculate_retry_delay(0) == 1.0
        assert database_node._calculate_retry_delay(1) == 2.0
        assert database_node._calculate_retry_delay(2) == 3.0

    def test_calculate_retry_delay_fibonacci(self, database_node):
        """Test Fibonacci retry delay calculation."""
        database_node.retry_config.strategy = RetryStrategy.FIBONACCI
        database_node.retry_config.base_delay = 1.0
        database_node.retry_config.jitter = False
        
        assert database_node._calculate_retry_delay(0) == 1.0  # fib(1) = 1
        assert database_node._calculate_retry_delay(1) == 2.0  # fib(2) = 2
        assert database_node._calculate_retry_delay(2) == 3.0  # fib(3) = 3

    def test_calculate_retry_delay_fixed(self, database_node):
        """Test fixed interval retry delay calculation."""
        database_node.retry_config.strategy = RetryStrategy.FIXED_INTERVAL
        database_node.retry_config.base_delay = 5.0
        database_node.retry_config.jitter = False
        
        assert database_node._calculate_retry_delay(0) == 5.0
        assert database_node._calculate_retry_delay(5) == 5.0

    def test_calculate_retry_delay_with_jitter(self, database_node):
        """Test retry delay calculation with jitter."""
        database_node.retry_config.strategy = RetryStrategy.FIXED_INTERVAL
        database_node.retry_config.base_delay = 10.0
        database_node.retry_config.jitter = True
        
        delay = database_node._calculate_retry_delay(0)
        # With jitter, delay should be between 5.0 and 10.0
        assert 5.0 <= delay <= 10.0

    def test_calculate_retry_delay_max_limit(self, database_node):
        """Test retry delay respects maximum limit."""
        database_node.retry_config.strategy = RetryStrategy.EXPONENTIAL_BACKOFF
        database_node.retry_config.base_delay = 1.0
        database_node.retry_config.backoff_multiplier = 2.0
        database_node.retry_config.max_delay = 5.0
        database_node.retry_config.jitter = False
        
        # This would normally be 8.0, but should be capped at 5.0
        delay = database_node._calculate_retry_delay(3)
        assert delay == 5.0

    def test_fibonacci_calculation(self, database_node):
        """Test Fibonacci number calculation."""
        assert database_node._fibonacci(0) == 0
        assert database_node._fibonacci(1) == 1
        assert database_node._fibonacci(2) == 1
        assert database_node._fibonacci(3) == 2
        assert database_node._fibonacci(4) == 3
        assert database_node._fibonacci(5) == 5
        assert database_node._fibonacci(6) == 8

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_first_attempt(self, database_node):
        """Test successful operation on first attempt."""
        async def mock_operation(conn):
            return "success"
            
        database_node.acquire_connection = AsyncMock()
        mock_conn = AsyncMock()
        database_node.acquire_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        database_node.acquire_connection.return_value.__aexit__ = AsyncMock()
        
        result = await database_node.execute_with_retry(mock_operation)
        
        assert result == "success"
        assert database_node.metrics.successful_queries == 1
        assert database_node.metrics.total_queries == 1
        assert database_node.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_after_failure(self, database_node):
        """Test successful operation after initial failure."""
        call_count = 0
        
        async def mock_operation(conn):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary failure")
            return "success"
            
        database_node.acquire_connection = AsyncMock()
        mock_conn = AsyncMock()
        database_node.acquire_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        database_node.acquire_connection.return_value.__aexit__ = AsyncMock()
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await database_node.execute_with_retry(mock_operation)
            
        assert result == "success"
        assert database_node.metrics.successful_queries == 1
        assert database_node.metrics.failed_queries == 1
        assert database_node.metrics.total_queries == 2

    @pytest.mark.asyncio
    async def test_execute_with_retry_all_attempts_fail(self, database_node):
        """Test operation failure on all retry attempts."""
        async def mock_operation(conn):
            raise Exception("Persistent failure")
            
        database_node.acquire_connection = AsyncMock()
        mock_conn = AsyncMock()
        database_node.acquire_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        database_node.acquire_connection.return_value.__aexit__ = AsyncMock()
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(Exception, match="Persistent failure"):
                await database_node.execute_with_retry(mock_operation)
                
        assert database_node.state == DatabaseConnectionState.FAILED
        assert database_node.metrics.failed_queries == 2  # max_attempts = 2
        assert database_node.metrics.successful_queries == 0

    @pytest.mark.asyncio
    async def test_health_check_success(self, database_node):
        """Test successful health check."""
        database_node.acquire_connection = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[1, 5])  # Health check and connection count
        database_node.acquire_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        database_node.acquire_connection.return_value.__aexit__ = AsyncMock()
        
        result = await database_node.health_check()
        
        assert result is True
        assert database_node.last_health_check is not None

    @pytest.mark.asyncio
    async def test_health_check_failure(self, database_node):
        """Test health check failure."""
        database_node.acquire_connection = AsyncMock()
        database_node.acquire_connection.return_value.__aenter__ = AsyncMock(side_effect=Exception("Connection failed"))
        
        result = await database_node.health_check()
        
        assert result is False

    def test_record_query_time(self, database_node):
        """Test query time recording and average calculation."""
        database_node._record_query_time(1.0)
        database_node._record_query_time(2.0)
        database_node._record_query_time(3.0)
        
        assert len(database_node.query_times) == 3
        assert database_node.metrics.average_query_time == 2.0

    def test_record_query_time_max_samples(self, database_node):
        """Test query time recording respects max samples."""
        database_node.max_query_time_samples = 2
        
        database_node._record_query_time(1.0)
        database_node._record_query_time(2.0)
        database_node._record_query_time(3.0)
        
        assert len(database_node.query_times) == 2
        assert database_node.query_times == [2.0, 3.0]

    def test_get_metrics(self, database_node):
        """Test metrics retrieval."""
        # Set up some test data
        database_node.metrics.total_queries = 100
        database_node.metrics.successful_queries = 95
        database_node.metrics.failed_queries = 5
        database_node.consecutive_failures = 2
        
        metrics = database_node.get_metrics()
        
        assert metrics["role"] == "primary"
        assert metrics["state"] == "healthy"
        assert metrics["consecutive_failures"] == 2
        assert metrics["metrics"]["total_queries"] == 100
        assert metrics["metrics"]["successful_queries"] == 95
        assert metrics["metrics"]["failed_queries"] == 5
        assert metrics["metrics"]["success_rate"] == 95.0


class TestDatabaseManager:
    """Test DatabaseManager functionality."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create mock configuration manager."""
        config_manager = Mock()
        config_manager.get.side_effect = lambda key, default=None: {
            "DATABASE_URL": "postgresql://primary:test@localhost/test",
            "DATABASE_REPLICA_URLS": "",
            "DATABASE_BACKUP_URLS": "",
            "APP_NAME": "test-app",
            "DATABASE_READ_STRATEGY": "round_robin"
        }.get(key, default)
        config_manager.get_int.side_effect = lambda key, default=None: {
            "DATABASE_MAX_RETRIES": 3,
            "DATABASE_POOL_SIZE": 20,
            "DATABASE_MIN_POOL_SIZE": 5,
            "DATABASE_HEALTH_CHECK_INTERVAL": 30
        }.get(key, default)
        config_manager.get_float.side_effect = lambda key, default=None: {
            "DATABASE_RETRY_DELAY": 1.0,
            "DATABASE_MAX_RETRY_DELAY": 60.0,
            "DATABASE_ACQUIRE_TIMEOUT": 30.0,
            "DATABASE_QUERY_TIMEOUT": 60.0,
            "DATABASE_COMMAND_TIMEOUT": 300.0
        }.get(key, default)
        config_manager.get_list.side_effect = lambda key, sep: []
        return config_manager

    @pytest.fixture
    def database_manager(self, mock_config_manager):
        """Create database manager for testing."""
        with patch('src.infrastructure.database.database_manager.get_config_manager', return_value=mock_config_manager):
            with patch('src.infrastructure.database.database_manager.get_logger'):
                with patch('src.infrastructure.database.database_manager.get_metrics_collector'):
                    return DatabaseManager()

    def test_manager_initialization(self, database_manager):
        """Test database manager initialization."""
        assert database_manager.primary_node is None
        assert database_manager.replica_nodes == []
        assert database_manager.backup_nodes == []
        assert database_manager.retry_config.max_attempts == 3
        assert database_manager.read_strategy == "round_robin"

    @pytest.mark.asyncio
    async def test_initialize_primary_only(self, database_manager):
        """Test initialization with primary database only."""
        mock_node = AsyncMock()
        mock_node.initialize = AsyncMock()
        
        with patch.object(DatabaseNode, '__new__', return_value=mock_node):
            await database_manager._initialize_primary_database()
            
        assert database_manager.primary_node == mock_node
        mock_node.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_with_replicas(self, database_manager, mock_config_manager):
        """Test initialization with replica databases."""
        mock_config_manager.get_list.side_effect = lambda key, sep: [
            "postgresql://replica1:test@localhost/test",
            "postgresql://replica2:test@localhost/test"
        ] if key == "DATABASE_REPLICA_URLS" else []
        
        mock_replica1 = AsyncMock()
        mock_replica2 = AsyncMock()
        mock_replica1.initialize = AsyncMock()
        mock_replica2.initialize = AsyncMock()
        
        with patch.object(DatabaseNode, '__new__', side_effect=[mock_replica1, mock_replica2]):
            await database_manager._initialize_replica_databases()
            
        assert len(database_manager.replica_nodes) == 2
        mock_replica1.initialize.assert_called_once()
        mock_replica2.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_write_success(self, database_manager):
        """Test successful write operation."""
        mock_primary = AsyncMock()
        mock_primary.execute_with_retry = AsyncMock(return_value="write_result")
        database_manager.primary_node = mock_primary
        
        async def mock_operation(conn):
            return "write_result"
            
        with patch('src.infrastructure.database.database_manager.audit_logger'):
            result = await database_manager.execute_write(mock_operation)
            
        assert result == "write_result"
        mock_primary.execute_with_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_write_primary_fails_backup_succeeds(self, database_manager):
        """Test write operation falls back to backup when primary fails."""
        mock_primary = AsyncMock()
        mock_primary.execute_with_retry = AsyncMock(side_effect=Exception("Primary failed"))
        
        mock_backup = AsyncMock()
        mock_backup.state = DatabaseConnectionState.HEALTHY
        mock_backup.execute_with_retry = AsyncMock(return_value="backup_result")
        
        database_manager.primary_node = mock_primary
        database_manager.backup_nodes = [mock_backup]
        
        async def mock_operation(conn):
            return "test"
            
        with patch('src.infrastructure.database.database_manager.audit_logger'):
            result = await database_manager.execute_write(mock_operation)
            
        assert result == "backup_result"
        mock_backup.execute_with_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_write_no_primary(self, database_manager):
        """Test write operation fails when no primary available."""
        database_manager.primary_node = None
        
        async def mock_operation(conn):
            return "test"
            
        with pytest.raises(ConnectionError, match="No primary database available"):
            await database_manager.execute_write(mock_operation)

    @pytest.mark.asyncio
    async def test_execute_read_from_replica(self, database_manager):
        """Test read operation uses replica database."""
        mock_replica = AsyncMock()
        mock_replica.state = DatabaseConnectionState.HEALTHY
        mock_replica.execute_with_retry = AsyncMock(return_value="replica_result")
        
        database_manager.replica_nodes = [mock_replica]
        
        async def mock_operation(conn):
            return "replica_result"
            
        with patch('src.infrastructure.database.database_manager.performance_logger'):
            result = await database_manager.execute_read(mock_operation)
            
        assert result == "replica_result"
        mock_replica.execute_with_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_read_fallback_to_primary(self, database_manager):
        """Test read operation falls back to primary when replica fails."""
        mock_replica = AsyncMock()
        mock_replica.state = DatabaseConnectionState.HEALTHY
        mock_replica.execute_with_retry = AsyncMock(side_effect=Exception("Replica failed"))
        
        mock_primary = AsyncMock()
        mock_primary.execute_with_retry = AsyncMock(return_value="primary_result")
        
        database_manager.replica_nodes = [mock_replica]
        database_manager.primary_node = mock_primary
        
        async def mock_operation(conn):
            return "test"
            
        with patch('src.infrastructure.database.database_manager.performance_logger'):
            result = await database_manager.execute_read(mock_operation)
            
        assert result == "primary_result"
        mock_primary.execute_with_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_read_no_database(self, database_manager):
        """Test read operation fails when no database available."""
        database_manager.replica_nodes = []
        database_manager.primary_node = None
        
        async def mock_operation(conn):
            return "test"
            
        with pytest.raises(ConnectionError, match="No database available for read operation"):
            await database_manager.execute_read(mock_operation)

    def test_select_replica_round_robin(self, database_manager):
        """Test round-robin replica selection."""
        mock_replica1 = Mock()
        mock_replica2 = Mock()
        mock_replica3 = Mock()
        
        replicas = [mock_replica1, mock_replica2, mock_replica3]
        database_manager.read_strategy = "round_robin"
        database_manager.current_replica_index = 0
        
        # Test round-robin selection
        assert database_manager._select_replica(replicas) == mock_replica1
        assert database_manager.current_replica_index == 1
        
        assert database_manager._select_replica(replicas) == mock_replica2
        assert database_manager.current_replica_index == 2
        
        assert database_manager._select_replica(replicas) == mock_replica3
        assert database_manager.current_replica_index == 3
        
        # Should wrap around
        assert database_manager._select_replica(replicas) == mock_replica1
        assert database_manager.current_replica_index == 4

    def test_select_replica_least_connections(self, database_manager):
        """Test least connections replica selection."""
        mock_replica1 = Mock()
        mock_replica1.metrics.active_connections = 10
        
        mock_replica2 = Mock()
        mock_replica2.metrics.active_connections = 5
        
        mock_replica3 = Mock()
        mock_replica3.metrics.active_connections = 8
        
        replicas = [mock_replica1, mock_replica2, mock_replica3]
        database_manager.read_strategy = "least_connections"
        
        selected = database_manager._select_replica(replicas)
        assert selected == mock_replica2  # Has least connections (5)

    def test_select_replica_fastest_response(self, database_manager):
        """Test fastest response replica selection."""
        mock_replica1 = Mock()
        mock_replica1.metrics.average_query_time = 0.5
        
        mock_replica2 = Mock()
        mock_replica2.metrics.average_query_time = 0.2
        
        mock_replica3 = Mock()
        mock_replica3.metrics.average_query_time = 0.8
        
        replicas = [mock_replica1, mock_replica2, mock_replica3]
        database_manager.read_strategy = "fastest_response"
        
        selected = database_manager._select_replica(replicas)
        assert selected == mock_replica2  # Has fastest response (0.2)

    def test_select_replica_default_strategy(self, database_manager):
        """Test default replica selection strategy."""
        mock_replica1 = Mock()
        mock_replica2 = Mock()
        
        replicas = [mock_replica1, mock_replica2]
        database_manager.read_strategy = "unknown_strategy"
        
        selected = database_manager._select_replica(replicas)
        assert selected == mock_replica1  # Default to first

    def test_select_replica_no_replicas(self, database_manager):
        """Test replica selection with no available replicas."""
        with pytest.raises(ValueError, match="No available replicas"):
            database_manager._select_replica([])

    @pytest.mark.asyncio
    async def test_health_check_loop_cancellation(self, database_manager):
        """Test health check loop handles cancellation."""
        database_manager.health_check_interval = 0.1
        
        with patch.object(database_manager, '_perform_health_checks', new_callable=AsyncMock) as mock_health_checks:
            # Start the health check loop
            task = asyncio.create_task(database_manager._health_check_loop())
            
            # Let it run briefly
            await asyncio.sleep(0.05)
            
            # Cancel the task
            task.cancel()
            
            # Wait for cancellation
            with pytest.raises(asyncio.CancelledError):
                await task

    @pytest.mark.asyncio
    async def test_perform_health_checks(self, database_manager):
        """Test health check performance on all nodes."""
        mock_primary = AsyncMock()
        mock_replica = AsyncMock()
        mock_backup = AsyncMock()
        
        database_manager.primary_node = mock_primary
        database_manager.replica_nodes = [mock_replica]
        database_manager.backup_nodes = [mock_backup]
        
        with patch.object(database_manager, '_check_node_health', new_callable=AsyncMock) as mock_check:
            await database_manager._perform_health_checks()
            
        assert mock_check.call_count == 3
        mock_check.assert_any_call(mock_primary)
        mock_check.assert_any_call(mock_replica)
        mock_check.assert_any_call(mock_backup)

    @pytest.mark.asyncio
    async def test_check_node_health_recovery(self, database_manager):
        """Test node health check handles recovery states."""
        mock_node = AsyncMock()
        mock_node.health_check = AsyncMock(return_value=True)
        mock_node.state = DatabaseConnectionState.FAILED
        mock_node.config.role.value = "primary"
        
        await database_manager._check_node_health(mock_node)
        
        assert mock_node.state == DatabaseConnectionState.RECOVERING

    @pytest.mark.asyncio
    async def test_check_node_health_degradation(self, database_manager):
        """Test node health check handles degradation."""
        mock_node = AsyncMock()
        mock_node.health_check = AsyncMock(return_value=False)
        mock_node.state = DatabaseConnectionState.HEALTHY
        mock_node.config.role.value = "primary"
        
        await database_manager._check_node_health(mock_node)
        
        assert mock_node.state == DatabaseConnectionState.DEGRADED

    def test_get_all_metrics(self, database_manager):
        """Test comprehensive metrics collection."""
        mock_primary = Mock()
        mock_primary.get_metrics.return_value = {
            "role": "primary",
            "state": "healthy",
            "metrics": {"total_connections": 10, "total_queries": 100}
        }
        mock_primary.state = DatabaseConnectionState.HEALTHY
        
        mock_replica = Mock()
        mock_replica.get_metrics.return_value = {
            "role": "replica",
            "state": "healthy",
            "metrics": {"total_connections": 5, "total_queries": 50}
        }
        mock_replica.state = DatabaseConnectionState.HEALTHY
        
        database_manager.primary_node = mock_primary
        database_manager.replica_nodes = [mock_replica]
        
        metrics = database_manager.get_all_metrics()
        
        assert len(metrics["nodes"]) == 2
        assert metrics["summary"]["total_nodes"] == 2
        assert metrics["summary"]["healthy_nodes"] == 2
        assert metrics["summary"]["failed_nodes"] == 0
        assert metrics["summary"]["total_connections"] == 15
        assert metrics["summary"]["total_queries"] == 150

    @pytest.mark.asyncio
    async def test_get_health_status_healthy(self, database_manager):
        """Test health status when all nodes are healthy."""
        mock_primary = Mock()
        mock_primary.state = DatabaseConnectionState.HEALTHY
        
        mock_replica = Mock()
        mock_replica.state = DatabaseConnectionState.HEALTHY
        
        database_manager.primary_node = mock_primary
        database_manager.replica_nodes = [mock_replica]
        
        status = await database_manager.get_health_status()
        
        assert status["status"] == "healthy"
        assert status["primary_available"] is True
        assert status["replicas_available"] == 1

    @pytest.mark.asyncio
    async def test_get_health_status_degraded(self, database_manager):
        """Test health status when some nodes failed."""
        mock_primary = Mock()
        mock_primary.state = DatabaseConnectionState.HEALTHY
        
        mock_replica = Mock()
        mock_replica.state = DatabaseConnectionState.FAILED
        
        database_manager.primary_node = mock_primary
        database_manager.replica_nodes = [mock_replica]
        
        status = await database_manager.get_health_status()
        
        assert status["status"] == "degraded"
        assert status["primary_available"] is True
        assert status["replicas_available"] == 0

    @pytest.mark.asyncio
    async def test_get_health_status_failed(self, database_manager):
        """Test health status when all nodes failed."""
        mock_primary = Mock()
        mock_primary.state = DatabaseConnectionState.FAILED
        
        database_manager.primary_node = mock_primary
        database_manager.replica_nodes = []
        
        status = await database_manager.get_health_status()
        
        assert status["status"] == "failed"
        assert status["primary_available"] is False

    @pytest.mark.asyncio
    async def test_close_manager(self, database_manager):
        """Test database manager closure."""
        mock_primary = AsyncMock()
        mock_replica = AsyncMock()
        mock_backup = AsyncMock()
        
        database_manager.primary_node = mock_primary
        database_manager.replica_nodes = [mock_replica]
        database_manager.backup_nodes = [mock_backup]
        
        # Mock running tasks
        database_manager.health_check_task = AsyncMock()
        database_manager.metrics_task = AsyncMock()
        
        await database_manager.close()
        
        database_manager.health_check_task.cancel.assert_called_once()
        database_manager.metrics_task.cancel.assert_called_once()
        mock_primary.close.assert_called_once()
        mock_replica.close.assert_called_once()
        mock_backup.close.assert_called_once()


class TestGlobalFunctions:
    """Test global database functions."""

    @pytest.mark.asyncio
    async def test_execute_query_read_only(self):
        """Test execute_query with read-only operation."""
        mock_manager = AsyncMock()
        mock_manager.execute_read = AsyncMock(return_value=[{"id": 1}])
        
        with patch('src.infrastructure.database.database_manager.get_database_manager', return_value=mock_manager):
            result = await execute_query("SELECT * FROM test", read_only=True)
            
        assert result == [{"id": 1}]
        mock_manager.execute_read.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_write(self):
        """Test execute_query with write operation."""
        mock_manager = AsyncMock()
        mock_manager.execute_write = AsyncMock(return_value="INSERT 1")
        
        with patch('src.infrastructure.database.database_manager.get_database_manager', return_value=mock_manager):
            result = await execute_query("INSERT INTO test VALUES (1)", read_only=False)
            
        assert result == "INSERT 1"
        mock_manager.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_one(self):
        """Test fetch_one function."""
        mock_manager = AsyncMock()
        mock_manager.execute_read = AsyncMock(return_value={"id": 1})
        
        with patch('src.infrastructure.database.database_manager.get_database_manager', return_value=mock_manager):
            result = await fetch_one("SELECT * FROM test WHERE id = $1", 1)
            
        assert result == {"id": 1}
        mock_manager.execute_read.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_all(self):
        """Test fetch_all function."""
        mock_manager = AsyncMock()
        mock_manager.execute_read = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        
        with patch('src.infrastructure.database.database_manager.get_database_manager', return_value=mock_manager):
            result = await fetch_all("SELECT * FROM test")
            
        assert result == [{"id": 1}, {"id": 2}]
        mock_manager.execute_read.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_command(self):
        """Test execute_command function."""
        mock_manager = AsyncMock()
        mock_manager.execute_write = AsyncMock(return_value="DELETE 1")
        
        with patch('src.infrastructure.database.database_manager.get_database_manager', return_value=mock_manager):
            result = await execute_command("DELETE FROM test WHERE id = $1", 1)
            
        assert result == "DELETE 1"
        mock_manager.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_connection_read_only_with_replica(self):
        """Test get_connection for read-only with replica available."""
        mock_manager = AsyncMock()
        mock_replica = Mock()
        mock_replica.state = DatabaseConnectionState.HEALTHY
        mock_replica.acquire_connection = AsyncMock()
        mock_conn = AsyncMock()
        mock_replica.acquire_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_replica.acquire_connection.return_value.__aexit__ = AsyncMock()
        
        mock_manager.replica_nodes = [mock_replica]
        mock_manager._select_replica = Mock(return_value=mock_replica)
        
        with patch('src.infrastructure.database.database_manager.get_database_manager', return_value=mock_manager):
            async with get_connection(read_only=True) as conn:
                assert conn == mock_conn

    @pytest.mark.asyncio
    async def test_get_connection_fallback_to_primary(self):
        """Test get_connection falls back to primary."""
        mock_manager = AsyncMock()
        mock_manager.replica_nodes = []
        mock_primary = Mock()
        mock_primary.acquire_connection = AsyncMock()
        mock_conn = AsyncMock()
        mock_primary.acquire_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_primary.acquire_connection.return_value.__aexit__ = AsyncMock()
        
        mock_manager.primary_node = mock_primary
        
        with patch('src.infrastructure.database.database_manager.get_database_manager', return_value=mock_manager):
            async with get_connection(read_only=True) as conn:
                assert conn == mock_conn

    @pytest.mark.asyncio
    async def test_get_connection_no_primary(self):
        """Test get_connection fails when no primary available."""
        mock_manager = AsyncMock()
        mock_manager.replica_nodes = []
        mock_manager.primary_node = None
        
        with patch('src.infrastructure.database.database_manager.get_database_manager', return_value=mock_manager):
            with pytest.raises(ConnectionError, match="No primary database available"):
                async with get_connection():
                    pass

    @pytest.mark.asyncio
    async def test_initialize_database(self):
        """Test initialize_database function."""
        mock_manager = AsyncMock()
        mock_manager.initialize = AsyncMock()
        
        with patch('src.infrastructure.database.database_manager.get_database_manager', return_value=mock_manager):
            await initialize_database()
            
        mock_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_database(self):
        """Test close_database function."""
        mock_manager = AsyncMock()
        mock_manager.close = AsyncMock()
        
        with patch('src.infrastructure.database.database_manager.get_database_manager', return_value=mock_manager):
            await close_database()
            
        mock_manager.close.assert_called_once()

    def test_get_database_manager_singleton(self):
        """Test get_database_manager returns singleton instance."""
        # Clear global instance
        import src.infrastructure.database.database_manager as db_module
        db_module.database_manager = None
        
        with patch('src.infrastructure.database.database_manager.get_config_manager'):
            with patch('src.infrastructure.database.database_manager.get_logger'):
                with patch('src.infrastructure.database.database_manager.get_metrics_collector'):
                    manager1 = get_database_manager()
                    manager2 = get_database_manager()
                    
        assert manager1 is manager2  # Same instance


class TestDatabaseManagerIntegration:
    """Integration tests for database manager workflows."""

    @pytest.mark.asyncio
    async def test_complete_database_lifecycle(self):
        """Test complete database manager lifecycle."""
        mock_config_manager = Mock()
        mock_config_manager.get.side_effect = lambda key, default=None: {
            "DATABASE_URL": "postgresql://test:test@localhost/test",
            "APP_NAME": "test-app"
        }.get(key, default)
        mock_config_manager.get_int.side_effect = lambda key, default=None: default or 10
        mock_config_manager.get_float.side_effect = lambda key, default=None: default or 30.0
        mock_config_manager.get_list.side_effect = lambda key, sep: []
        
        with patch('src.infrastructure.database.database_manager.get_config_manager', return_value=mock_config_manager):
            with patch('src.infrastructure.database.database_manager.get_logger'):
                with patch('src.infrastructure.database.database_manager.get_metrics_collector'):
                    with patch.object(DatabaseNode, 'initialize', new_callable=AsyncMock):
                        with patch.object(DatabaseNode, 'close', new_callable=AsyncMock):
                            manager = DatabaseManager()
                            
                            # Initialize
                            await manager.initialize()
                            assert manager.primary_node is not None
                            
                            # Get health status
                            status = await manager.get_health_status()
                            assert "status" in status
                            
                            # Get metrics
                            metrics = manager.get_all_metrics()
                            assert "nodes" in metrics
                            assert "summary" in metrics
                            
                            # Close
                            await manager.close()

    @pytest.mark.asyncio
    async def test_failover_scenario(self):
        """Test database failover scenario."""
        mock_config_manager = Mock()
        mock_config_manager.get.side_effect = lambda key, default=None: {
            "DATABASE_URL": "postgresql://primary:test@localhost/test",
            "DATABASE_BACKUP_URLS": "postgresql://backup:test@localhost/test"
        }.get(key, default)
        mock_config_manager.get_int.side_effect = lambda key, default=None: default or 10
        mock_config_manager.get_float.side_effect = lambda key, default=None: default or 30.0
        mock_config_manager.get_list.side_effect = lambda key, sep: [
            "postgresql://backup:test@localhost/test"
        ] if key == "DATABASE_BACKUP_URLS" else []
        
        with patch('src.infrastructure.database.database_manager.get_config_manager', return_value=mock_config_manager):
            with patch('src.infrastructure.database.database_manager.get_logger'):
                with patch('src.infrastructure.database.database_manager.get_metrics_collector'):
                    with patch('src.infrastructure.database.database_manager.audit_logger'):
                        manager = DatabaseManager()
                        
                        # Mock primary node failure
                        mock_primary = AsyncMock()
                        mock_primary.execute_with_retry = AsyncMock(side_effect=Exception("Primary failed"))
                        
                        # Mock backup node success
                        mock_backup = AsyncMock()
                        mock_backup.state = DatabaseConnectionState.HEALTHY
                        mock_backup.execute_with_retry = AsyncMock(return_value="backup_success")
                        
                        manager.primary_node = mock_primary
                        manager.backup_nodes = [mock_backup]
                        
                        async def test_operation(conn):
                            return "test_result"
                        
                        # Should failover to backup
                        result = await manager.execute_write(test_operation)
                        assert result == "backup_success"
                        
                        # Both primary and backup should have been called
                        mock_primary.execute_with_retry.assert_called_once()
                        mock_backup.execute_with_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_balancing_scenario(self):
        """Test load balancing across replicas."""
        manager = DatabaseManager()
        manager.read_strategy = "round_robin"
        manager.current_replica_index = 0
        
        # Create mock replicas
        mock_replica1 = AsyncMock()
        mock_replica1.state = DatabaseConnectionState.HEALTHY
        mock_replica1.execute_with_retry = AsyncMock(return_value="replica1_result")
        
        mock_replica2 = AsyncMock()  
        mock_replica2.state = DatabaseConnectionState.HEALTHY
        mock_replica2.execute_with_retry = AsyncMock(return_value="replica2_result")
        
        manager.replica_nodes = [mock_replica1, mock_replica2]
        
        async def test_operation(conn):
            return "test_result"
            
        with patch('src.infrastructure.database.database_manager.performance_logger'):
            # First call should use replica1
            result1 = await manager.execute_read(test_operation)
            assert result1 == "replica1_result"
            
            # Second call should use replica2
            result2 = await manager.execute_read(test_operation)
            assert result2 == "replica2_result"
            
            # Third call should wrap back to replica1
            result3 = await manager.execute_read(test_operation)
            assert result3 == "replica1_result"
        
        # Verify round-robin behavior
        assert manager.current_replica_index == 3
        mock_replica1.execute_with_retry.call_count == 2
        mock_replica2.execute_with_retry.call_count == 1


class TestDatabaseManagerEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_initialization_failure_recovery(self):
        """Test initialization failure and recovery."""
        mock_config_manager = Mock()
        mock_config_manager.get.return_value = "postgresql://invalid"
        mock_config_manager.get_int.side_effect = lambda key, default=None: default or 10
        mock_config_manager.get_float.side_effect = lambda key, default=None: default or 30.0
        mock_config_manager.get_list.side_effect = lambda key, sep: []
        
        with patch('src.infrastructure.database.database_manager.get_config_manager', return_value=mock_config_manager):
            with patch('src.infrastructure.database.database_manager.get_logger'):
                with patch('src.infrastructure.database.database_manager.get_metrics_collector'):
                    manager = DatabaseManager()
                    
                    # Mock initialization failure
                    with patch.object(DatabaseNode, 'initialize', side_effect=Exception("Init failed")):
                        with pytest.raises(Exception, match="Init failed"):
                            await manager.initialize()

    def test_metrics_reporting_error_handling(self):
        """Test metrics reporting handles errors gracefully."""
        manager = DatabaseManager()
        
        # Mock metrics collector that raises exception
        mock_collector = Mock()
        mock_collector.gauge.side_effect = Exception("Metrics error")
        manager.metrics_collector = mock_collector
        
        # Mock nodes with metrics
        mock_node = Mock()
        mock_node.get_metrics.return_value = {
            "role": "primary",
            "metrics": {
                "total_connections": 10,
                "active_connections": 5,
                "peak_connections": 15,
                "total_queries": 100,
                "successful_queries": 95,
                "failed_queries": 5,
                "average_query_time": 0.1,
                "success_rate": 95.0
            }
        }
        manager.primary_node = mock_node
        
        # Should not raise exception despite metrics error
        asyncio.run(manager._report_metrics())

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent database operations."""
        manager = DatabaseManager()
        
        mock_primary = AsyncMock()
        mock_primary.execute_with_retry = AsyncMock(return_value="write_result")
        manager.primary_node = mock_primary
        
        mock_replica = AsyncMock()
        mock_replica.state = DatabaseConnectionState.HEALTHY
        mock_replica.execute_with_retry = AsyncMock(return_value="read_result")
        manager.replica_nodes = [mock_replica]
        
        async def write_operation(conn):
            await asyncio.sleep(0.01)  # Simulate work
            return "write_result"
            
        async def read_operation(conn):
            await asyncio.sleep(0.01)  # Simulate work
            return "read_result"
        
        with patch('src.infrastructure.database.database_manager.audit_logger'):
            with patch('src.infrastructure.database.database_manager.performance_logger'):
                # Run concurrent operations
                tasks = [
                    manager.execute_write(write_operation),
                    manager.execute_read(read_operation),
                    manager.execute_read(read_operation),
                    manager.execute_write(write_operation)
                ]
                
                results = await asyncio.gather(*tasks)
                
        assert results == ["write_result", "read_result", "read_result", "write_result"]
        assert mock_primary.execute_with_retry.call_count == 2  # Two writes
        assert mock_replica.execute_with_retry.call_count == 2   # Two reads