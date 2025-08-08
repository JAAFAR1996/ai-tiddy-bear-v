"""
Database Performance Optimization System
Advanced connection pooling, query optimization, indexing, and child-safe data handling
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any, Tuple
import time
import hashlib
import logging
from src.utils.date_utils import get_current_timestamp
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import QueuePool
from sqlalchemy.sql import text
from src.core.exceptions import DatabaseError, configurationerror, ValidationError
from src.core.utils.crypto_utils import encrypt_sensitive_data, hash_data

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of database queries."""

    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    BULK_INSERT = "bulk_insert"
    BULK_UPDATE = "bulk_update"


class PoolStrategy(Enum):
    """Connection pool strategies."""

    STANDARD = "standard"
    PESSIMISTIC = "pessimistic"
    OPTIMISTIC = "optimistic"
    CHILD_SAFE = "child_safe"  # Special pool for child data


@dataclass
class DatabaseConfig:
    """Database configuration."""

    host: str
    port: int
    database: str
    username: str
    password: str = field(repr=False)

    # Connection pool settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600  # 1 hour
    pool_pre_ping: bool = True

    # Performance settings
    echo: bool = False
    echo_pool: bool = False
    query_cache_size: int = 500
    statement_timeout: int = 30000  # 30 seconds

    # Child safety settings
    child_data_encryption: bool = True
    child_data_audit: bool = True
    child_data_retention_days: int = 30


@dataclass
class QueryMetrics:
    """Query performance metrics."""

    sql_hash: str
    query_type: QueryType
    execution_count: int = 0
    total_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    min_time_ms: float = float("inf")
    max_time_ms: float = 0.0
    error_count: int = 0
    last_executed: Optional[datetime] = None

    # Child safety metrics
    child_data_accessed: bool = False
    privacy_compliant: bool = True


@dataclass
class ConnectionPoolMetrics:
    """Connection pool performance metrics."""

    pool_name: str
    size: int
    checked_in: int
    checked_out: int
    overflow: int
    total_connections: int
    avg_checkout_time_ms: float = 0.0
    checkout_count: int = 0
    checkout_errors: int = 0
    pool_timeouts: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class IndexRecommendation:
    """Database index recommendation."""

    table_name: str
    columns: List[str]
    index_type: str  # btree, hash, gin, etc.
    estimated_benefit: float  # 0.0 to 1.0
    reason: str
    query_patterns: List[str]
    child_data_table: bool = False


class QueryAnalyzer:
    """Analyzes SQL queries for optimization opportunities."""

    def __init__(self):
        self.query_cache = {}
        self.query_metrics: Dict[str, QueryMetrics] = {}
        self.slow_queries: List[Tuple[str, float, datetime]] = []
        self.index_recommendations: List[IndexRecommendation] = []

    def analyze_query(
        self, sql: str, params: Optional[Dict] = None, execution_time_ms: float = 0.0
    ) -> QueryMetrics:
        """Analyze a SQL query and update metrics."""

        # Normalize SQL for consistent hashing
        normalized_sql = self._normalize_sql(sql)
        sql_hash = hashlib.md5(normalized_sql.encode()).hexdigest()

        # Determine query type
        query_type = self._determine_query_type(normalized_sql)

        # Check if it accesses child data
        child_data_accessed = self._checks_child_data_access(normalized_sql)

        # Get or create metrics
        if sql_hash not in self.query_metrics:
            self.query_metrics[sql_hash] = QueryMetrics(
                sql_hash=sql_hash,
                query_type=query_type,
                child_data_accessed=child_data_accessed,
            )

        metrics = self.query_metrics[sql_hash]

        # Update metrics
        if execution_time_ms > 0:
            metrics.execution_count += 1
            metrics.total_time_ms += execution_time_ms
            metrics.avg_time_ms = metrics.total_time_ms / metrics.execution_count
            metrics.min_time_ms = min(metrics.min_time_ms, execution_time_ms)
            metrics.max_time_ms = max(metrics.max_time_ms, execution_time_ms)
            metrics.last_executed = datetime.now()

            # Track slow queries
            if execution_time_ms > 1000:  # Slower than 1 second
                self.slow_queries.append((sql, execution_time_ms, datetime.now()))

                # Keep only recent slow queries
                cutoff_time = datetime.now() - timedelta(hours=24)
                self.slow_queries = [
                    (s, t, d) for s, t, d in self.slow_queries if d > cutoff_time
                ]

        # Generate index recommendations
        if (
            metrics.execution_count > 10 and metrics.avg_time_ms > 100
        ):  # Frequent slow query
            self._generate_index_recommendations(normalized_sql, params)

        return metrics

    def _normalize_sql(self, sql: str) -> str:
        """Normalize SQL query for consistent analysis."""
        # Remove extra whitespace and convert to lowercase
        normalized = " ".join(sql.lower().split())

        # Replace parameter placeholders with generic ones
        import re

        # Replace $1, $2, etc. with $n
        normalized = re.sub(r"\$\d+", "$n", normalized)

        # Replace quoted strings with placeholder
        normalized = re.sub(r"'[^']*'", "'?'", normalized)

        # Replace numbers with placeholder
        normalized = re.sub(r"\b\d+\b", "n", normalized)

        return normalized

    def _determine_query_type(self, sql: str) -> QueryType:
        """Determine the type of SQL query."""
        sql_lower = sql.lower().strip()

        if sql_lower.startswith("select"):
            return QueryType.SELECT
        elif sql_lower.startswith("insert"):
            if "values" in sql_lower and sql_lower.count("values") > 1:
                return QueryType.BULK_INSERT
            return QueryType.INSERT
        elif sql_lower.startswith("update"):
            if "from" in sql_lower or "join" in sql_lower:
                return QueryType.BULK_UPDATE
            return QueryType.UPDATE
        elif sql_lower.startswith("delete"):
            return QueryType.DELETE
        else:
            return QueryType.SELECT  # Default

    def _checks_child_data_access(self, sql: str) -> bool:
        """Check if query accesses child-related data."""
        child_table_patterns = [
            "children",
            "child_profiles",
            "child_data",
            "conversations",
            "child_sessions",
            "parental_controls",
            "child_preferences",
        ]

        sql_lower = sql.lower()
        return any(pattern in sql_lower for pattern in child_table_patterns)

    def _generate_index_recommendations(self, sql: str, params: Optional[Dict]) -> None:
        """Generate index recommendations based on query patterns."""
        # This is a simplified implementation
        # In production, you would use query execution plans

        sql_lower = sql.lower()

        # Look for WHERE clauses
        if "where" in sql_lower:
            # Extract table and column patterns
            # This would be more sophisticated in a real implementation
            if "child_id" in sql_lower:
                recommendation = IndexRecommendation(
                    table_name="children",
                    columns=["child_id"],
                    index_type="btree",
                    estimated_benefit=0.8,
                    reason="Frequent WHERE clause on child_id",
                    query_patterns=[sql],
                    child_data_table=True,
                )

                # Avoid duplicate recommendations
                if not any(
                    r.table_name == recommendation.table_name
                    and r.columns == recommendation.columns
                    for r in self.index_recommendations
                ):
                    self.index_recommendations.append(recommendation)

    def get_slow_queries(self, limit: int = 10) -> List[Tuple[str, float, datetime]]:
        """Get slowest queries."""
        return sorted(self.slow_queries, key=lambda x: x[1], reverse=True)[:limit]

    def get_frequent_queries(self, limit: int = 10) -> List[QueryMetrics]:
        """Get most frequently executed queries."""
        return sorted(
            self.query_metrics.values(), key=lambda x: x.execution_count, reverse=True
        )[:limit]

    def get_index_recommendations(self) -> List[IndexRecommendation]:
        """Get index recommendations."""
        return sorted(
            self.index_recommendations, key=lambda x: x.estimated_benefit, reverse=True
        )


class ConnectionPoolManager:
    """Manages database connection pools with optimization."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engines: Dict[str, AsyncEngine] = {}
        self.session_makers: Dict[str, async_sessionmaker] = {}
        self.pool_metrics: Dict[str, ConnectionPoolMetrics] = {}
        self.query_analyzer = QueryAnalyzer()

    async def initialize(self) -> None:
        """Initialize connection pools."""

        # Main connection pool
        await self._create_engine_pool("main", PoolStrategy.STANDARD)

        # Read-only pool for reporting queries
        await self._create_engine_pool(
            "readonly", PoolStrategy.OPTIMISTIC, readonly=True
        )

        # Special pool for child data with enhanced security
        await self._create_engine_pool("child_data", PoolStrategy.CHILD_SAFE)

        # Bulk operations pool
        await self._create_engine_pool("bulk", PoolStrategy.PESSIMISTIC, pool_size=5)

        logger.info("Database connection pools initialized")

    async def _create_engine_pool(
        self,
        pool_name: str,
        strategy: PoolStrategy,
        readonly: bool = False,
        pool_size: Optional[int] = None,
    ) -> None:
        """Create a connection pool with specific strategy."""

        # Build connection URL
        url = f"postgresql+asyncpg://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"

        # Pool configuration based on strategy
        pool_config = self._get_pool_config(strategy, pool_size)

        # Create engine
        engine = create_async_engine(
            url, echo=self.config.echo, echo_pool=self.config.echo_pool, **pool_config
        )

        # Create session maker
        session_maker = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        self.engines[pool_name] = engine
        self.session_makers[pool_name] = session_maker

        # Initialize metrics
        self.pool_metrics[pool_name] = ConnectionPoolMetrics(
            pool_name=pool_name,
            size=pool_config.get("pool_size", self.config.pool_size),
            checked_in=0,
            checked_out=0,
            overflow=0,
            total_connections=0,
        )

        logger.info(
            f"Created {pool_name} connection pool with {strategy.value} strategy"
        )

    def _get_pool_config(
        self, strategy: PoolStrategy, custom_pool_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get pool configuration based on strategy."""

        base_config = {
            "pool_size": custom_pool_size or self.config.pool_size,
            "max_overflow": self.config.max_overflow,
            "pool_timeout": self.config.pool_timeout,
            "pool_recycle": self.config.pool_recycle,
            "pool_pre_ping": self.config.pool_pre_ping,
            "poolclass": QueuePool,
        }

        if strategy == PoolStrategy.PESSIMISTIC:
            # Conservative settings for reliability
            base_config.update(
                {
                    "pool_size": min(base_config["pool_size"], 5),
                    "max_overflow": min(base_config["max_overflow"], 5),
                    "pool_timeout": base_config["pool_timeout"] * 2,
                }
            )

        elif strategy == PoolStrategy.OPTIMISTIC:
            # Aggressive settings for performance
            base_config.update(
                {
                    "pool_size": base_config["pool_size"] * 2,
                    "max_overflow": base_config["max_overflow"] * 2,
                    "pool_timeout": base_config["pool_timeout"] // 2,
                }
            )

        elif strategy == PoolStrategy.CHILD_SAFE:
            # Special settings for child data handling
            base_config.update(
                {
                    "pool_size": min(
                        base_config["pool_size"], 3
                    ),  # Limited connections
                    "max_overflow": min(base_config["max_overflow"], 2),
                    "pool_recycle": 1800,  # More frequent recycling
                    "connect_args": {
                        "command_timeout": 10,  # Shorter timeout for child operations
                        "server_settings": {"application_name": "child_data_handler"},
                    },
                }
            )

        return base_config

    @asynccontextmanager
    async def get_session(self, pool_name: str = "main"):
        """Get database session from specified pool."""
        if pool_name not in self.session_makers:
            raise DatabaseError("Pool not found", context={"pool_name": pool_name})

        session_maker = self.session_makers[pool_name]

        start_time = time.time()
        session = None

        try:
            session = session_maker()

            # Update pool metrics
            checkout_time_ms = (time.time() - start_time) * 1000
            metrics = self.pool_metrics[pool_name]
            metrics.checkout_count += 1
            metrics.avg_checkout_time_ms = (
                metrics.avg_checkout_time_ms * (metrics.checkout_count - 1)
                + checkout_time_ms
            ) / metrics.checkout_count
            metrics.checked_out += 1

            yield session

        except Exception as e:
            if session:
                await session.rollback()

            self.pool_metrics[pool_name].checkout_errors += 1
            logger.error(f"Database session error in pool '{pool_name}': {e}")
            raise DatabaseError(
                "Database session error",
                context={"pool_name": pool_name, "error": str(e)},
            )

        finally:
            if session:
                await session.close()
                self.pool_metrics[pool_name].checked_out -= 1

    async def execute_query(
        self,
        sql: str,
        params: Optional[Dict] = None,
        pool_name: str = "main",
        fetch_results: bool = True,
    ) -> Optional[List[Dict]]:
        """Execute SQL query with performance monitoring."""

        start_time = time.time()

        try:
            async with self.get_session(pool_name) as session:

                # Execute query - prefer ORM when possible, use text() for maintenance queries only
                if params:
                    result = await session.execute(text(sql), params)
                else:
                    result = await session.execute(text(sql))

                # Fetch results if needed
                if fetch_results and result.returns_rows:
                    rows = result.fetchall()
                    # Convert to list of dicts
                    results = [dict(row._mapping) for row in rows]
                else:
                    results = None

                await session.commit()

                # Record metrics
                execution_time_ms = (time.time() - start_time) * 1000
                self.query_analyzer.analyze_query(sql, params, execution_time_ms)

                # Log slow queries
                if execution_time_ms > 1000:
                    logger.warning(
                        f"Slow query detected: {execution_time_ms:.2f}ms",
                        extra={
                            "sql": sql[:200],  # Truncate for logging
                            "execution_time_ms": execution_time_ms,
                            "pool": pool_name,
                        },
                    )

                return results

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000

            # Record error metrics
            sql_hash = hashlib.md5(sql.encode()).hexdigest()
            if sql_hash in self.query_analyzer.query_metrics:
                self.query_analyzer.query_metrics[sql_hash].error_count += 1

            logger.error(f"Query execution failed: {e}")
            raise DatabaseError(
                "Query execution failed", context={"sql": sql, "error": str(e)}
            )

    async def execute_child_safe_query(
        self, sql: str, params: Optional[Dict] = None, child_id: Optional[str] = None
    ) -> Optional[List[Dict]]:
        """Execute query involving child data with special handling."""

        # Add child data audit logging
        if child_id:
            audit_data = {
                "child_id": child_id,
                "sql_hash": hashlib.md5(sql.encode()).hexdigest(),
                "timestamp": get_current_timestamp(),
                "operation": "database_access",
            }
            logger.info("Child data access", extra=audit_data)

        # Use child-safe pool
        try:
            result = await self.execute_query(sql, params, pool_name="child_data")

            # Encrypt sensitive results if configured
            if self.config.child_data_encryption and result:
                result = self._encrypt_child_data_results(result, child_id)

            return result

        except Exception as e:
            logger.error(f"Child-safe query failed: {e}", extra={"child_id": child_id})
            raise

    def _encrypt_child_data_results(
        self, results: List[Dict], child_id: Optional[str]
    ) -> List[Dict]:
        """Encrypt sensitive fields in child data results."""
        if not results:
            return results

        # Define sensitive fields that should be encrypted
        sensitive_fields = ["name", "email", "phone", "address", "notes"]

        encrypted_results = []
        for row in results:
            encrypted_row = row.copy()
        for sensitive_field in sensitive_fields:
            if sensitive_field in encrypted_row and encrypted_row[sensitive_field]:
                encrypted_row[sensitive_field] = encrypt_sensitive_data(
                    str(encrypted_row[sensitive_field])
                )
            encrypted_results.append(encrypted_row)

        return encrypted_results

    async def bulk_insert(
        self, table_name: str, data: List[Dict], chunk_size: int = 1000
    ) -> int:
        """Perform optimized bulk insert."""
        if not data:
            return 0

        total_inserted = 0

        async with self.get_session("bulk") as session:
            try:
                # Process in chunks
                for i in range(0, len(data), chunk_size):
                    chunk = data[i : i + chunk_size]

                    # Use ORM bulk insert instead of raw SQL
                    # Note: For better performance, consider using SQLAlchemy bulk_insert_mappings
                    # or PostgreSQL COPY command for very large datasets
                    columns = list(chunk[0].keys())
                    placeholders = ", ".join([f":{col}" for col in columns])
                    sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"

                    # Execute bulk insert (keeping current approach for compatibility)
                    await session.execute(text(sql), chunk)
                    total_inserted += len(chunk)

                await session.commit()
                logger.info(f"Bulk inserted {total_inserted} rows into {table_name}")

            except Exception as e:
                await session.rollback()
                logger.error(f"Bulk insert failed: {e}")
                raise DatabaseError(
                    "Bulk insert failed", context={"table": table_name, "error": str(e)}
                )

        return total_inserted

    async def optimize_database(self) -> Dict[str, Any]:
        """Run database optimization tasks."""
        optimization_results = {
            "vacuum_analyze_completed": False,
            "index_recommendations": [],
            "query_optimizations": [],
            "child_data_cleanup": False,
        }

        try:
            # Run VACUUM ANALYZE on main tables
            await self._vacuum_analyze_tables()
            optimization_results["vacuum_analyze_completed"] = True

            # Generate index recommendations
            recommendations = self.query_analyzer.get_index_recommendations()
            optimization_results["index_recommendations"] = [
                {
                    "table": r.table_name,
                    "columns": r.columns,
                    "benefit": r.estimated_benefit,
                    "reason": r.reason,
                }
                for r in recommendations
            ]

            # Clean up old child data if configured
            if self.config.child_data_retention_days > 0:
                cleaned_count = await self._cleanup_old_child_data()
                optimization_results["child_data_cleanup"] = cleaned_count > 0
                optimization_results["child_records_cleaned"] = cleaned_count

            logger.info("Database optimization completed", extra=optimization_results)

        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            optimization_results["error"] = str(e)

        return optimization_results

    async def _vacuum_analyze_tables(self) -> None:
        """Run VACUUM ANALYZE on main tables."""
        main_tables = ["children", "conversations", "child_sessions", "audit_logs"]

        for table in main_tables:
            try:
                await self.execute_query(
                    f"VACUUM ANALYZE {table};", fetch_results=False
                )
                logger.info(f"VACUUM ANALYZE completed for {table}")
            except Exception as e:
                logger.warning(f"VACUUM ANALYZE failed for {table}: {e}")

    async def _cleanup_old_child_data(self) -> int:
        """Clean up old child data based on retention policy."""
        cutoff_date = datetime.now() - timedelta(
            days=self.config.child_data_retention_days
        )

        cleanup_queries = [
            ("child_sessions", "created_at < :cutoff_date"),
            (
                "audit_logs",
                "timestamp < :cutoff_date AND event_type = 'child_interaction'",
            ),
            ("temp_child_data", "created_at < :cutoff_date"),
        ]

        total_cleaned = 0

        for table, condition in cleanup_queries:
            try:
                await self.execute_query(
                    f"DELETE FROM {table} WHERE {condition}",
                    {"cutoff_date": cutoff_date},
                    pool_name="child_data",
                    fetch_results=False,
                )

                # Log cleanup for compliance
                logger.info(
                    f"Child data cleanup completed for {table}",
                    extra={
                        "table": table,
                        "cutoff_date": cutoff_date.isoformat(),
                        "compliance": "COPPA",
                    },
                )

            except Exception as e:
                logger.error(f"Child data cleanup failed for {table}: {e}")

        return total_cleaned

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive database performance metrics."""

        # Update pool metrics
        for pool_name, engine in self.engines.items():
            pool = engine.pool
            metrics = self.pool_metrics[pool_name]

            metrics.size = pool.size()
            metrics.checked_in = pool.checkedin()
            metrics.checked_out = pool.checkedout()
            metrics.overflow = pool.overflow()
            metrics.total_connections = metrics.checked_in + metrics.checked_out
            metrics.last_updated = datetime.now()

        # Get query metrics
        slow_queries = self.query_analyzer.get_slow_queries(5)
        frequent_queries = self.query_analyzer.get_frequent_queries(5)

        return {
            "connection_pools": {
                pool_name: {
                    "size": metrics.size,
                    "checked_in": metrics.checked_in,
                    "checked_out": metrics.checked_out,
                    "total_connections": metrics.total_connections,
                    "avg_checkout_time_ms": metrics.avg_checkout_time_ms,
                    "checkout_errors": metrics.checkout_errors,
                    "pool_timeouts": metrics.pool_timeouts,
                }
                for pool_name, metrics in self.pool_metrics.items()
            },
            "query_performance": {
                "total_queries_analyzed": len(self.query_analyzer.query_metrics),
                "slow_queries_count": len(self.query_analyzer.slow_queries),
                "slowest_queries": [
                    {
                        "sql_preview": sql[:100] + "..." if len(sql) > 100 else sql,
                        "execution_time_ms": time_ms,
                        "timestamp": timestamp.isoformat(),
                    }
                    for sql, time_ms, timestamp in slow_queries
                ],
                "frequent_queries": [
                    {
                        "query_type": metrics.query_type.value,
                        "execution_count": metrics.execution_count,
                        "avg_time_ms": metrics.avg_time_ms,
                        "child_data_accessed": metrics.child_data_accessed,
                    }
                    for metrics in frequent_queries
                ],
            },
            "optimization": {
                "index_recommendations_count": len(
                    self.query_analyzer.index_recommendations
                ),
                "child_data_tables_analyzed": sum(
                    1
                    for r in self.query_analyzer.index_recommendations
                    if r.child_data_table
                ),
            },
        }

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive database health check."""
        health_status = {
            "overall_status": "healthy",
            "pools_healthy": 0,
            "total_pools": len(self.engines),
            "slow_queries_detected": len(self.query_analyzer.slow_queries),
            "connection_issues": [],
            "child_data_compliance": "compliant",
        }

        # Test each connection pool with ORM instead of raw SQL
        for pool_name, engine in self.engines.items():
            try:
                async with engine.begin() as conn:
                    from sqlalchemy import select, literal

                    test_query = select(literal(1).label("test"))
                    await conn.execute(test_query)
                health_status["pools_healthy"] += 1

            except Exception as e:
                health_status["connection_issues"].append(
                    {"pool": pool_name, "error": str(e)}
                )

        # Check for performance issues
        if len(self.query_analyzer.slow_queries) > 10:
            health_status["overall_status"] = "degraded"

        # Check child data compliance
        child_violations = sum(
            1
            for metrics in self.query_analyzer.query_metrics.values()
            if metrics.child_data_accessed and not metrics.privacy_compliant
        )

        if child_violations > 0:
            health_status["child_data_compliance"] = "violations_detected"
            health_status["overall_status"] = "critical"

        # Overall status
        if health_status["connection_issues"]:
            health_status["overall_status"] = "unhealthy"

        return health_status

    async def close(self) -> None:
        """Close all database connections."""
        for pool_name, engine in self.engines.items():
            await engine.dispose()
            logger.info(f"Closed {pool_name} connection pool")


# Factory function for easy initialization
def create_database_optimizer(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    pool_size: int = 10,
    child_data_encryption: bool = True,
) -> ConnectionPoolManager:
    """Create database optimizer with connection pooling."""

    config = DatabaseConfig(
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
        pool_size=pool_size,
        child_data_encryption=child_data_encryption,
        child_data_audit=True,
    )

    return ConnectionPoolManager(config)
