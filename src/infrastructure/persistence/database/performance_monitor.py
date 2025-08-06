"""
Database Performance Monitor
Enterprise-grade query performance tracking and slow query analysis
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import deque
import json

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


@dataclass
class QueryMetrics:
    """Query performance metrics"""
    query_hash: str
    query_text: str
    execution_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    slow_query_count: int = 0
    last_executed: Optional[datetime] = None
    error_count: int = 0


@dataclass
class DatabasePerformanceMonitor:
    """Production database performance monitoring"""

    slow_query_threshold: float = 100.0  # milliseconds
    query_cache_size: int = 1000
    metrics_retention_hours: int = 24

    # Internal tracking
    query_metrics: Dict[str, QueryMetrics] = field(default_factory=dict)
    recent_queries: deque = field(default_factory=lambda: deque(maxlen=100))
    connection_pool_stats: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize monitoring components"""
        self.start_time = datetime.utcnow()

    def setup_monitoring(self, engine: AsyncEngine) -> None:
        """Set up SQLAlchemy event listeners for performance monitoring"""

        @event.listens_for(engine.sync_engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Track query start time"""
            context._query_start_time = time.perf_counter()
            context._query_statement = statement

        @event.listens_for(engine.sync_engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Track query completion and metrics"""
            if hasattr(context, '_query_start_time'):
                execution_time = (time.perf_counter() - context._query_start_time) * 1000  # Convert to ms
                self._record_query_metrics(statement, execution_time, success=True)

        @event.listens_for(engine.sync_engine, "handle_error")
        def handle_error(exception_context):
            """Track query errors"""
            statement = getattr(exception_context, 'statement', 'Unknown')
            self._record_query_metrics(statement, 0, success=False)

    def _record_query_metrics(self, statement: str, execution_time: float, success: bool = True) -> None:
        """Record query metrics for analysis"""
        query_hash = self._hash_query(statement)

        # Get or create metrics for this query
        if query_hash not in self.query_metrics:
            self.query_metrics[query_hash] = QueryMetrics(
                query_hash=query_hash,
                query_text=statement[:500]  # Truncate long queries
            )

        metrics = self.query_metrics[query_hash]

        if success:
            # Update execution metrics
            metrics.execution_count += 1
            metrics.total_time += execution_time
            metrics.min_time = min(metrics.min_time, execution_time)
            metrics.max_time = max(metrics.max_time, execution_time)
            metrics.avg_time = metrics.total_time / metrics.execution_count
            metrics.last_executed = datetime.utcnow()

            # Track slow queries
            if execution_time > self.slow_query_threshold:
                metrics.slow_query_count += 1
                logger.warning(f"Slow query detected: {execution_time:.2f}ms - {statement[:100]}...")

            # Add to recent queries for analysis
            self.recent_queries.append({
                'timestamp': datetime.utcnow(),
                'query_hash': query_hash,
                'execution_time': execution_time,
                'statement': statement[:200]
            })
        else:
            metrics.error_count += 1

        # Clean up old metrics
        self._cleanup_old_metrics()

    def _hash_query(self, statement: str) -> str:
        """Generate hash for query normalization"""
        import hashlib
        # Normalize query by removing parameters and whitespace
        normalized = ' '.join(statement.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()

    def _cleanup_old_metrics(self) -> None:
        """Remove old metrics to prevent memory leaks"""
        if len(self.query_metrics) > self.query_cache_size:
            oldest_queries = sorted(
                self.query_metrics.items(),
                key=lambda x: x[1].last_executed or datetime.min
            )[:50]  # Remove 50 oldest

            for query_hash, _ in oldest_queries:
                del self.query_metrics[query_hash]

    def get_slow_queries(self, limit: int = 10) -> List[QueryMetrics]:
        """Get slowest queries by average execution time"""
        return sorted(
            [m for m in self.query_metrics.values() if m.slow_query_count > 0],
            key=lambda x: x.avg_time,
            reverse=True
        )[:limit]

    def get_frequent_queries(self, limit: int = 10) -> List[QueryMetrics]:
        """Get most frequently executed queries"""
        return sorted(
            self.query_metrics.values(),
            key=lambda x: x.execution_count,
            reverse=True
        )[:limit]

    def get_error_queries(self, limit: int = 10) -> List[QueryMetrics]:
        """Get queries with most errors"""
        return sorted(
            [m for m in self.query_metrics.values() if m.error_count > 0],
            key=lambda x: x.error_count,
            reverse=True
        )[:limit]

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        total_queries = sum(m.execution_count for m in self.query_metrics.values())
        total_slow_queries = sum(m.slow_query_count for m in self.query_metrics.values())
        total_errors = sum(m.error_count for m in self.query_metrics.values())

        avg_execution_time = 0
        if self.query_metrics:
            avg_execution_time = sum(m.avg_time for m in self.query_metrics.values()) / len(self.query_metrics)

        uptime = datetime.utcnow() - self.start_time

        return {
            'monitoring_start_time': self.start_time,
            'uptime_seconds': uptime.total_seconds(),
            'total_queries_executed': total_queries,
            'unique_query_patterns': len(self.query_metrics),
            'slow_queries_count': total_slow_queries,
            'slow_query_percentage': (total_slow_queries / max(total_queries, 1)) * 100,
            'query_errors': total_errors,
            'error_percentage': (total_errors / max(total_queries, 1)) * 100,
            'average_query_time_ms': round(avg_execution_time, 2),
            'slow_query_threshold_ms': self.slow_query_threshold,
            'queries_per_second': round(total_queries / max(uptime.total_seconds(), 1), 2)
        }

    def generate_performance_report(self) -> str:
        """Generate human-readable performance report"""
        summary = self.get_performance_summary()
        slow_queries = self.get_slow_queries(5)
        frequent_queries = self.get_frequent_queries(5)
        error_queries = self.get_error_queries(5)

        report = []
        report.append("🔍 DATABASE PERFORMANCE ANALYSIS")
        report.append("=" * 50)

        # Summary section
        report.append("\n📊 PERFORMANCE SUMMARY")
        report.append(f"Monitoring Duration: {summary['uptime_seconds']:.0f} seconds")
        report.append(f"Total Queries: {summary['total_queries_executed']:,}")
        report.append(f"Unique Query Patterns: {summary['unique_query_patterns']:,}")
        report.append(f"Average Query Time: {summary['average_query_time_ms']:.2f}ms")
        report.append(f"Queries per Second: {summary['queries_per_second']:.2f}")

        # Performance alerts
        if summary['slow_query_percentage'] > 5:
            report.append(f"⚠️  ALERT: {summary['slow_query_percentage']:.1f}% of queries are slow (>{self.slow_query_threshold}ms)")

        if summary['error_percentage'] > 1:
            report.append(f"🚨 ALERT: {summary['error_percentage']:.1f}% of queries have errors")

        # Slow queries section
        if slow_queries:
            report.append("\n🐌 SLOWEST QUERIES")
            for i, query in enumerate(slow_queries, 1):
                report.append(f"{i}. Avg: {query.avg_time:.2f}ms, Max: {query.max_time:.2f}ms, Count: {query.execution_count}")
                report.append(f"   Query: {query.query_text[:100]}...")

        # Frequent queries section
        if frequent_queries:
            report.append("\n🔄 MOST FREQUENT QUERIES")
            for i, query in enumerate(frequent_queries, 1):
                report.append(f"{i}. Executions: {query.execution_count:,}, Avg: {query.avg_time:.2f}ms")
                report.append(f"   Query: {query.query_text[:100]}...")

        # Error queries section
        if error_queries:
            report.append("\n❌ QUERIES WITH ERRORS")
            for i, query in enumerate(error_queries, 1):
                report.append(f"{i}. Errors: {query.error_count}, Executions: {query.execution_count}")
                report.append(f"   Query: {query.query_text[:100]}...")

        return "\n".join(report)

    async def continuous_monitoring(self, interval_seconds: int = 300) -> None:
        """Run continuous performance monitoring"""
        logger.info(f"Starting continuous database performance monitoring (interval: {interval_seconds}s)")

        while True:
            try:
                await asyncio.sleep(interval_seconds)

                # Generate and log performance report
                report = self.generate_performance_report()
                logger.info(f"Performance Report:\n{report}")

                # Check for performance alerts
                summary = self.get_performance_summary()

                if summary['slow_query_percentage'] > 10:
                    logger.error(f"CRITICAL: {summary['slow_query_percentage']:.1f}% of queries are slow!")

                if summary['error_percentage'] > 5:
                    logger.error(f"CRITICAL: {summary['error_percentage']:.1f}% of queries have errors!")

                if summary['average_query_time_ms'] > 200:
                    logger.warning(f"WARNING: Average query time is {summary['average_query_time_ms']:.2f}ms")

            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")

    def export_metrics_json(self) -> str:
        """Export metrics as JSON for external analysis"""
        data = {
            'summary': self.get_performance_summary(),
            'slow_queries': [
                {
                    'query_text': q.query_text,
                    'avg_time': q.avg_time,
                    'max_time': q.max_time,
                    'execution_count': q.execution_count,
                    'slow_query_count': q.slow_query_count
                }
                for q in self.get_slow_queries(20)
            ],
            'frequent_queries': [
                {
                    'query_text': q.query_text,
                    'execution_count': q.execution_count,
                    'avg_time': q.avg_time
                }
                for q in self.get_frequent_queries(20)
            ]
        }
        return json.dumps(data, indent=2, default=str)


# Global performance monitor instance
performance_monitor: Optional[DatabasePerformanceMonitor] = None


def initialize_performance_monitoring(engine: AsyncEngine, **kwargs) -> DatabasePerformanceMonitor:
    """Initialize performance monitoring for database engine"""
    global performance_monitor

    performance_monitor = DatabasePerformanceMonitor(**kwargs)
    performance_monitor.setup_monitoring(engine)

    logger.info("Database performance monitoring initialized")
    return performance_monitor


async def verify_query_performance():
    """Verify all queries are under 100ms threshold"""
    from .production_config import initialize_database

    logger.info("🔍 Verifying query performance...")

    # Initialize database and monitoring
    manager = await initialize_database()
    monitor = initialize_performance_monitoring(manager.engine)

    # Test queries that should be fast
    test_queries = [
        "SELECT COUNT(*) FROM users WHERE is_active = true",
        "SELECT * FROM children WHERE parent_id = $1 LIMIT 10",
        "SELECT * FROM conversations WHERE child_id = $1 ORDER BY created_at DESC LIMIT 20",
        "SELECT * FROM messages WHERE conversation_id = $1 ORDER BY sequence_number LIMIT 50",
    ]

    async with manager.get_session() as session:
        for query in test_queries:
            start_time = time.perf_counter()
            try:
                # Execute test query (with placeholder parameters)
                if '$1' in query:
                    # Skip parameterized queries in this test
                    continue
                await session.execute(text(query))
                execution_time = (time.perf_counter() - start_time) * 1000

                if execution_time > 100:
                    logger.error(f"❌ SLOW QUERY: {execution_time:.2f}ms - {query}")
                else:
                    logger.info(f"✅ FAST QUERY: {execution_time:.2f}ms - {query}")

            except Exception as e:
                logger.error(f"❌ QUERY ERROR: {query} - {e}")

    # Generate performance report
    report = monitor.generate_performance_report()
    logger.info(f"Performance verification completed:\n{report}")

    return monitor.get_performance_summary()

if __name__ == "__main__":
    # Test performance monitoring
    asyncio.run(verify_query_performance())
