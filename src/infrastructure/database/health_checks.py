"""
Database Health Checks - Production Database Health Monitoring
==============================================================
Comprehensive health monitoring for database infrastructure:
- Connection pool health monitoring
- Query performance monitoring
- Transaction health checks
- COPPA compliance validation
- Data integrity checks
- Migration status validation
- Deadlock detection and reporting
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from .database_manager import database_manager, DatabaseConnectionState
from . import transaction_manager, migration_manager
from ..config.config_manager_provider import get_config_manager
from ..logging import get_logger, audit_logger, security_logger


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Health check result."""
    check_name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    duration_ms: float
    timestamp: datetime
    recommendations: List[str]


class DatabaseHealthChecker:
    """Comprehensive database health checker."""
    
    def __init__(self, config=None):
        self.config = config  # Inject config via DI
        self.logger = get_logger("database_health_checker")
        
        # Health check configuration with safe defaults
        self.connection_timeout = getattr(config, "HEALTH_CHECK_CONNECTION_TIMEOUT", 5.0) if config else 5.0
        self.query_timeout = getattr(config, "HEALTH_CHECK_QUERY_TIMEOUT", 10.0) if config else 10.0
        self.max_acceptable_latency = getattr(config, "HEALTH_CHECK_MAX_LATENCY", 100.0) if config else 100.0
        self.critical_error_threshold = getattr(config, "HEALTH_CHECK_ERROR_THRESHOLD", 5) if config else 5
        
        # COPPA compliance checks
        self.coppa_compliance_enabled = getattr(config, "COPPA_COMPLIANCE_ENABLED", True) if config else True
        self.child_data_retention_days = getattr(config, "CHILD_DATA_RETENTION_DAYS", 90) if config else 90
    
    async def run_comprehensive_health_check(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks and return comprehensive results."""
        self.logger.info("Starting comprehensive database health check")
        
        health_checks = {
            "connection_pool": self._check_connection_pool_health,
            "query_performance": self._check_query_performance,
            "transaction_health": self._check_transaction_health,
            "migration_status": self._check_migration_status,
            "data_integrity": self._check_data_integrity,
            "deadlock_detection": self._check_for_deadlocks,
            "coppa_compliance": self._check_coppa_compliance,
            "disk_space": self._check_disk_space,
            "replication_lag": self._check_replication_lag,
            "security_validation": self._check_security_validation
        }
        
        results = {}
        
        # Run health checks concurrently
        tasks = []
        for check_name, check_function in health_checks.items():
            task = asyncio.create_task(self._run_single_health_check(check_name, check_function))
            tasks.append(task)
        
        check_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, (check_name, _) in enumerate(health_checks.items()):
            result = check_results[i]
            if isinstance(result, Exception):
                results[check_name] = HealthCheckResult(
                    check_name=check_name,
                    status=HealthStatus.CRITICAL,
                    message=f"Health check failed: {str(result)}",
                    details={"error": str(result)},
                    duration_ms=0.0,
                    timestamp=datetime.now(),
                    recommendations=["Investigate health check failure", "Check system logs"]
                )
            else:
                results[check_name] = result
        
        # Log overall health status
        overall_status = self._determine_overall_health_status(results)
        self.logger.info(
            f"Database health check completed - Overall status: {overall_status.value}",
            extra={
                "total_checks": len(results),
                "healthy_checks": len([r for r in results.values() if r.status == HealthStatus.HEALTHY]),
                "warning_checks": len([r for r in results.values() if r.status == HealthStatus.WARNING]),
                "critical_checks": len([r for r in results.values() if r.status == HealthStatus.CRITICAL])
            }
        )
        
        return results
    
    async def _run_single_health_check(self, check_name: str, check_function) -> HealthCheckResult:
        """Run a single health check with timing and error handling."""
        start_time = time.time()
        
        try:
            result = await check_function()
            result.duration_ms = (time.time() - start_time) * 1000
            result.timestamp = datetime.now()
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.error(f"Health check '{check_name}' failed: {str(e)}")
            
            return HealthCheckResult(
                check_name=check_name,
                status=HealthStatus.CRITICAL,
                message=f"Health check exception: {str(e)}",
                details={"exception": str(e), "type": type(e).__name__},
                duration_ms=duration_ms,
                timestamp=datetime.now(),
                recommendations=["Check system logs", "Verify database connectivity"]
            )
    
    async def _check_connection_pool_health(self) -> HealthCheckResult:
        """Check connection pool health across all database nodes."""
        details = {}
        recommendations = []
        issues = []
        
        # Check primary node
        if database_manager.primary_node:
            primary_metrics = database_manager.primary_node.get_metrics()
            details["primary"] = primary_metrics
            
            if primary_metrics["state"] != DatabaseConnectionState.HEALTHY.value:
                issues.append(f"Primary database is {primary_metrics['state']}")
                recommendations.append("Investigate primary database connectivity")
            
            pool_utilization = (
                primary_metrics["metrics"]["active_connections"] / 
                primary_metrics["pool_info"].get("pool_max_size", 1) * 100
            )
            
            if pool_utilization > 80:
                issues.append(f"High pool utilization: {pool_utilization:.1f}%")
                recommendations.append("Consider increasing connection pool size")
        else:
            issues.append("No primary database configured")
            recommendations.append("Configure primary database connection")
        
        # Check replica nodes
        details["replicas"] = []
        healthy_replicas = 0
        
        for i, replica in enumerate(database_manager.replica_nodes):
            replica_metrics = replica.get_metrics()
            details["replicas"].append(replica_metrics)
            
            if replica_metrics["state"] == DatabaseConnectionState.HEALTHY.value:
                healthy_replicas += 1
            else:
                issues.append(f"Replica {i+1} is {replica_metrics['state']}")
        
        details["healthy_replicas"] = healthy_replicas
        details["total_replicas"] = len(database_manager.replica_nodes)
        
        # Determine status
        if not issues:
            status = HealthStatus.HEALTHY
            message = "All database connections are healthy"
        elif len(issues) == 1 and "High pool utilization" in issues[0]:
            status = HealthStatus.WARNING
            message = f"Connection pool health warning: {issues[0]}"
        else:
            status = HealthStatus.CRITICAL
            message = f"Connection pool issues detected: {'; '.join(issues)}"
        
        return HealthCheckResult(
            check_name="connection_pool",
            status=status,
            message=message,
            details=details,
            duration_ms=0.0,
            timestamp=datetime.now(),
            recommendations=recommendations
        )
    
    async def _check_query_performance(self) -> HealthCheckResult:
        """Check database query performance."""
        test_queries = [
            ("SELECT 1", "Basic connectivity"),
            ("SELECT COUNT(*) FROM information_schema.tables", "Schema access"),
            ("SELECT pg_database_size(current_database())", "Database size query"),
            ("SELECT NOW()", "Time function")
        ]
        
        details = {"query_results": []}
        slow_queries = []
        failed_queries = []
        
        for query, description in test_queries:
            start_time = time.time()
            
            try:
                result = await database_manager.execute_read(
                    lambda conn, q: conn.fetchval(q), query
                )
                
                execution_time = (time.time() - start_time) * 1000  # ms
                
                query_result = {
                    "description": description,
                    "query": query,
                    "execution_time_ms": execution_time,
                    "success": True,
                    "result": str(result) if result is not None else "NULL"
                }
                
                details["query_results"].append(query_result)
                
                if execution_time > self.max_acceptable_latency:
                    slow_queries.append(f"{description}: {execution_time:.1f}ms")
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                
                query_result = {
                    "description": description,
                    "query": query,
                    "execution_time_ms": execution_time,
                    "success": False,
                    "error": str(e)
                }
                
                details["query_results"].append(query_result)
                failed_queries.append(f"{description}: {str(e)}")
        
        recommendations = []
        
        # Determine status
        if failed_queries:
            status = HealthStatus.CRITICAL
            message = f"Query failures detected: {'; '.join(failed_queries)}"
            recommendations.extend([
                "Check database connectivity",
                "Verify database permissions",
                "Review database logs"
            ])
        elif slow_queries:
            status = HealthStatus.WARNING
            message = f"Slow queries detected: {'; '.join(slow_queries)}"
            recommendations.extend([
                "Review query performance",
                "Check database load",
                "Consider query optimization"
            ])
        else:
            status = HealthStatus.HEALTHY
            message = "All queries executing within acceptable performance limits"
        
        avg_execution_time = sum(
            result["execution_time_ms"] 
            for result in details["query_results"] 
            if result["success"]
        ) / len([r for r in details["query_results"] if r["success"]])
        
        details["average_execution_time_ms"] = avg_execution_time
        details["total_queries"] = len(test_queries)
        details["successful_queries"] = len([r for r in details["query_results"] if r["success"]])
        details["failed_queries"] = len(failed_queries)
        details["slow_queries"] = len(slow_queries)
        
        return HealthCheckResult(
            check_name="query_performance",
            status=status,
            message=message,
            details=details,
            duration_ms=0.0,
            timestamp=datetime.now(),
            recommendations=recommendations
        )
    
    async def _check_transaction_health(self) -> HealthCheckResult:
        """Check transaction system health."""
        details = {}
        recommendations = []
        issues = []
        
        # Get transaction metrics
        tx_metrics = transaction_manager.get_transaction_metrics()
        details["transaction_metrics"] = tx_metrics
        
        # Test basic transaction functionality
        try:
            async with transaction_manager.transaction() as tx:
                # Simple transaction test
                from sqlalchemy import text
                result = await tx.execute(text("SELECT 1 as test_value"))
                details["transaction_test"] = {
                    "success": True,
                    "result": "Transaction test completed successfully"
                }
        except Exception as e:
            details["transaction_test"] = {
                "success": False,
                "error": str(e)
            }
            issues.append(f"Transaction test failed: {str(e)}")
            recommendations.append("Check transaction manager configuration")
        
        # Analyze transaction metrics
        if tx_metrics.get("total_transactions", 0) > 0:
            success_rate = tx_metrics.get("success_rate", 0)
            if success_rate < 95:
                issues.append(f"Low transaction success rate: {success_rate:.1f}%")
                recommendations.append("Investigate transaction failures")
            
            avg_duration = tx_metrics.get("average_duration_ms", 0)
            if avg_duration > 1000:  # 1 second
                issues.append(f"High average transaction duration: {avg_duration:.1f}ms")
                recommendations.append("Optimize transaction performance")
            
            total_deadlocks = tx_metrics.get("total_deadlocks", 0)
            if total_deadlocks > 0:
                issues.append(f"Deadlocks detected: {total_deadlocks}")
                recommendations.append("Review application locking patterns")
        
        # Check active transactions
        active_transactions = tx_metrics.get("active_transactions", 0)
        if active_transactions > 10:
            issues.append(f"High number of active transactions: {active_transactions}")
            recommendations.append("Monitor for long-running transactions")
        
        details["active_transactions"] = active_transactions
        details["issues_detected"] = len(issues)
        
        # Determine status
        if not issues:
            status = HealthStatus.HEALTHY
            message = "Transaction system is healthy"
        elif len(issues) == 1 and "High average" in issues[0]:
            status = HealthStatus.WARNING
            message = f"Transaction performance warning: {issues[0]}"
        else:
            status = HealthStatus.CRITICAL
            message = f"Transaction issues detected: {'; '.join(issues)}"
        
        return HealthCheckResult(
            check_name="transaction_health",
            status=status,
            message=message,
            details=details,
            duration_ms=0.0,
            timestamp=datetime.now(),
            recommendations=recommendations
        )
    
    async def _check_migration_status(self) -> HealthCheckResult:
        """Check database migration status."""
        details = {}
        recommendations = []
        issues = []
        
        try:
            # Get migration status
            migration_records = await migration_manager.get_migration_status()
            details["migration_records"] = [
                {
                    "version": record.version,
                    "name": record.name,
                    "status": record.status.value,
                    "applied_at": record.applied_at.isoformat() if record.applied_at else None,
                    "execution_time_ms": record.execution_time_ms
                }
                for record in migration_records
            ]
            
            # Check for pending migrations
            pending_migrations = await migration_manager.get_pending_migrations()
            details["pending_migrations_count"] = len(pending_migrations)
            
            if pending_migrations:
                issues.append(f"{len(pending_migrations)} pending migrations")
                recommendations.append("Apply pending database migrations")
            
            # Check for failed migrations
            failed_migrations = [
                record for record in migration_records 
                if record.status.value == "failed"
            ]
            
            if failed_migrations:
                issues.append(f"{len(failed_migrations)} failed migrations")
                recommendations.extend([
                    "Investigate failed migrations",
                    "Review migration error logs",
                    "Consider migration rollback if necessary"
                ])
            
            # Validate migration integrity
            validation_results = await migration_manager.validate_migrations()
            invalid_migrations = [
                version for version, is_valid in validation_results.items() 
                if not is_valid
            ]
            
            if invalid_migrations:
                issues.append(f"Invalid migrations: {', '.join(invalid_migrations)}")
                recommendations.append("Re-run migration validation")
            
            details["total_migrations"] = len(migration_records)
            details["failed_migrations"] = len(failed_migrations)
            details["invalid_migrations"] = len(invalid_migrations)
            
        except Exception as e:
            issues.append(f"Migration status check failed: {str(e)}")
            recommendations.append("Check migration system configuration")
            details["error"] = str(e)
        
        # Determine status
        if not issues:
            status = HealthStatus.HEALTHY
            message = "All migrations applied successfully"
        elif any("pending" in issue for issue in issues):
            status = HealthStatus.WARNING
            message = f"Migration warnings: {'; '.join(issues)}"
        else:
            status = HealthStatus.CRITICAL
            message = f"Migration issues detected: {'; '.join(issues)}"
        
        return HealthCheckResult(
            check_name="migration_status",
            status=status,
            message=message,
            details=details,
            duration_ms=0.0,
            timestamp=datetime.now(),
            recommendations=recommendations
        )
    
    async def _check_data_integrity(self) -> HealthCheckResult:
        """Check basic data integrity."""
        details = {}
        recommendations = []
        issues = []
        
        try:
            # Check for orphaned records
            orphan_checks = [
                ("messages", "conversation_id", "conversations", "id", "Messages without conversations"),
                ("children", "parent_id", "users", "id", "Children without parents"),
                ("safety_reports", "child_id", "children", "id", "Safety reports without children")
            ]
            
            details["orphan_checks"] = []
            
            for child_table, child_fk, parent_table, parent_pk, description in orphan_checks:
                orphan_query = f"""
                    SELECT COUNT(*) 
                    FROM {child_table} c 
                    LEFT JOIN {parent_table} p ON c.{child_fk} = p.{parent_pk} 
                    WHERE p.{parent_pk} IS NULL AND c.{child_fk} IS NOT NULL
                """
                
                try:
                    orphan_count = await database_manager.execute_read(
                        lambda conn, q: conn.fetchval(q), orphan_query
                    )
                    
                    orphan_check = {
                        "description": description,
                        "orphan_count": orphan_count,
                        "child_table": child_table,
                        "parent_table": parent_table
                    }
                    
                    details["orphan_checks"].append(orphan_check)
                    
                    if orphan_count > 0:
                        issues.append(f"{orphan_count} {description.lower()}")
                        recommendations.append(f"Clean up orphaned records in {child_table}")
                
                except Exception as e:
                    self.logger.warning(f"Orphan check failed for {child_table}: {str(e)}")
            
            # Check for duplicate records
            duplicate_checks = [
                ("users", "username", "Duplicate usernames"),
                ("users", "email", "Duplicate emails"),
                ("children", "hashed_identifier", "Duplicate child identifiers")
            ]
            
            details["duplicate_checks"] = []
            
            for table, column, description in duplicate_checks:
                duplicate_query = f"""
                    SELECT COUNT(*) 
                    FROM (
                        SELECT {column} 
                        FROM {table} 
                        WHERE {column} IS NOT NULL 
                        GROUP BY {column} 
                        HAVING COUNT(*) > 1
                    ) duplicates
                """
                
                try:
                    duplicate_count = await database_manager.execute_read(
                        lambda conn, q: conn.fetchval(q), duplicate_query
                    )
                    
                    duplicate_check = {
                        "description": description,
                        "duplicate_count": duplicate_count,
                        "table": table,
                        "column": column
                    }
                    
                    details["duplicate_checks"].append(duplicate_check)
                    
                    if duplicate_count > 0:
                        issues.append(f"{duplicate_count} {description.lower()}")
                        recommendations.append(f"Resolve duplicate {column} in {table}")
                
                except Exception as e:
                    self.logger.warning(f"Duplicate check failed for {table}.{column}: {str(e)}")
            
            details["total_issues"] = len(issues)
            
        except Exception as e:
            issues.append(f"Data integrity check failed: {str(e)}")
            recommendations.append("Check database connectivity and permissions")
            details["error"] = str(e)
        
        # Determine status
        if not issues:
            status = HealthStatus.HEALTHY
            message = "Data integrity checks passed"
        elif len(issues) <= 2:
            status = HealthStatus.WARNING
            message = f"Minor data integrity issues: {'; '.join(issues)}"
        else:
            status = HealthStatus.CRITICAL
            message = f"Multiple data integrity issues: {'; '.join(issues)}"
        
        return HealthCheckResult(
            check_name="data_integrity",
            status=status,
            message=message,
            details=details,
            duration_ms=0.0,
            timestamp=datetime.now(),
            recommendations=recommendations
        )
    
    async def _check_for_deadlocks(self) -> HealthCheckResult:
        """Check for database deadlocks."""
        details = {}
        recommendations = []
        issues = []
        
        try:
            # Query for current blocking locks
            deadlock_query = """
                SELECT 
                    blocked_locks.pid AS blocked_pid,
                    blocked_activity.usename AS blocked_user,
                    blocking_locks.pid AS blocking_pid,
                    blocking_activity.usename AS blocking_user,
                    blocked_activity.query AS blocked_statement,
                    blocking_activity.query AS blocking_statement,
                    EXTRACT(EPOCH FROM (NOW() - blocked_activity.query_start)) as blocked_duration
                FROM pg_catalog.pg_locks blocked_locks
                JOIN pg_catalog.pg_stat_activity blocked_activity 
                    ON blocked_activity.pid = blocked_locks.pid
                JOIN pg_catalog.pg_locks blocking_locks 
                    ON blocking_locks.locktype = blocked_locks.locktype
                    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
                    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
                    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
                    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
                    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
                    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
                    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
                    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
                    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
                    AND blocking_locks.pid != blocked_locks.pid
                JOIN pg_catalog.pg_stat_activity blocking_activity 
                    ON blocking_activity.pid = blocking_locks.pid
                WHERE NOT blocked_locks.granted
                AND blocking_locks.granted
                AND blocked_activity.state = 'active'
                AND blocking_activity.state = 'active'
            """
            
            deadlocks = await database_manager.execute_read(
                lambda conn, q: conn.fetch(q), deadlock_query
            )
            
            details["active_deadlocks"] = len(deadlocks)
            details["deadlock_details"] = []
            
            for deadlock in deadlocks:
                deadlock_info = {
                    "blocked_pid": deadlock["blocked_pid"],
                    "blocking_pid": deadlock["blocking_pid"],
                    "blocked_user": deadlock["blocked_user"],
                    "blocking_user": deadlock["blocking_user"],
                    "blocked_duration": deadlock["blocked_duration"],
                    "blocked_query": deadlock["blocked_statement"][:100] + "..." if len(deadlock["blocked_statement"]) > 100 else deadlock["blocked_statement"],
                    "blocking_query": deadlock["blocking_statement"][:100] + "..." if len(deadlock["blocking_statement"]) > 100 else deadlock["blocking_statement"]
                }
                
                details["deadlock_details"].append(deadlock_info)
                
                if deadlock["blocked_duration"] > 30:  # 30 seconds
                    issues.append(f"Long-running deadlock: PID {deadlock['blocked_pid']} blocked for {deadlock['blocked_duration']:.1f}s")
            
            if deadlocks:
                recommendations.extend([
                    "Monitor deadlock resolution",
                    "Review application locking patterns",
                    "Consider query optimization",
                    "Implement deadlock retry logic"
                ])
            
            # Check for high lock count
            lock_count_query = "SELECT COUNT(*) FROM pg_locks"
            total_locks = await database_manager.execute_read(
                lambda conn, q: conn.fetchval(q), lock_count_query
            )
            
            details["total_locks"] = total_locks
            
            if total_locks > 1000:  # Threshold for high lock count
                issues.append(f"High lock count: {total_locks}")
                recommendations.append("Investigate high lock usage")
            
        except Exception as e:
            issues.append(f"Deadlock check failed: {str(e)}")
            recommendations.append("Check database monitoring permissions")
            details["error"] = str(e)
        
        # Determine status
        if not issues:
            status = HealthStatus.HEALTHY
            message = "No deadlocks detected"
        elif any("High lock count" in issue for issue in issues):
            status = HealthStatus.WARNING
            message = f"Lock management warnings: {'; '.join(issues)}"
        else:
            status = HealthStatus.CRITICAL
            message = f"Deadlock issues detected: {'; '.join(issues)}"
        
        return HealthCheckResult(
            check_name="deadlock_detection",
            status=status,
            message=message,
            details=details,
            duration_ms=0.0,
            timestamp=datetime.now(),
            recommendations=recommendations
        )
    
    async def _check_coppa_compliance(self) -> HealthCheckResult:
        """Check COPPA compliance status."""
        if not self.coppa_compliance_enabled:
            return HealthCheckResult(
                check_name="coppa_compliance",
                status=HealthStatus.HEALTHY,
                message="COPPA compliance checking disabled",
                details={"enabled": False},
                duration_ms=0.0,
                timestamp=datetime.now(),
                recommendations=[]
            )
        
        details = {"enabled": True}
        recommendations = []
        issues = []
        
        try:
            # Check for children without parental consent
            no_consent_query = """
                SELECT COUNT(*) FROM children 
                WHERE parental_consent = false 
                AND estimated_age < 13 
                AND is_deleted = false
            """
            
            no_consent_count = await database_manager.execute_read(
                lambda conn, q: conn.fetchval(q), no_consent_query
            )
            
            details["children_without_consent"] = no_consent_count
            
            if no_consent_count > 0:
                issues.append(f"{no_consent_count} children under 13 without parental consent")
                recommendations.append("Ensure parental consent for all children under 13")
            
            # Check for data retention violations
            retention_cutoff = datetime.now() - timedelta(days=self.child_data_retention_days)
            expired_data_query = """
                SELECT COUNT(*) FROM children 
                WHERE created_at < $1 
                AND retention_status = 'active' 
                AND is_deleted = false
            """
            
            expired_data_count = await database_manager.execute_read(
                lambda conn, q, cutoff: conn.fetchval(q, cutoff), 
                expired_data_query, 
                retention_cutoff
            )
            
            details["expired_data_records"] = expired_data_count
            details["retention_days"] = self.child_data_retention_days
            
            if expired_data_count > 0:
                issues.append(f"{expired_data_count} child records exceed retention period")
                recommendations.append("Schedule deletion of expired child data")
            
            # Check for missing child safety reports
            safety_check_query = """
                SELECT COUNT(*) FROM conversations c
                LEFT JOIN safety_reports sr ON c.id = sr.conversation_id
                WHERE c.child_id IS NOT NULL 
                AND c.flagged_content = true 
                AND sr.id IS NULL
            """
            
            missing_reports_count = await database_manager.execute_read(
                lambda conn, q: conn.fetchval(q), safety_check_query
            )
            
            details["missing_safety_reports"] = missing_reports_count
            
            if missing_reports_count > 0:
                issues.append(f"{missing_reports_count} flagged conversations without safety reports")
                recommendations.append("Create safety reports for flagged content")
            
            # Check audit log coverage for child data operations
            recent_child_ops_query = """
                SELECT COUNT(*) FROM audit_logs 
                WHERE involves_child_data = true 
                AND created_at > NOW() - INTERVAL '24 hours'
            """
            
            recent_child_ops = await database_manager.execute_read(
                lambda conn, q: conn.fetchval(q), recent_child_ops_query
            )
            
            details["recent_child_data_operations"] = recent_child_ops
            
            # Log COPPA compliance check
            security_logger.info(
                "COPPA compliance check completed",
                extra={
                    "children_without_consent": no_consent_count,
                    "expired_data_records": expired_data_count,
                    "missing_safety_reports": missing_reports_count,
                    "recent_child_operations": recent_child_ops
                }
            )
            
        except Exception as e:
            issues.append(f"COPPA compliance check failed: {str(e)}")
            recommendations.append("Check COPPA compliance system configuration")
            details["error"] = str(e)
        
        # Determine status
        if not issues:
            status = HealthStatus.HEALTHY
            message = "COPPA compliance checks passed"
        elif any("missing safety reports" in issue for issue in issues):
            status = HealthStatus.WARNING
            message = f"COPPA compliance warnings: {'; '.join(issues)}"
        else:
            status = HealthStatus.CRITICAL
            message = f"COPPA compliance violations: {'; '.join(issues)}"
        
        return HealthCheckResult(
            check_name="coppa_compliance",
            status=status,
            message=message,
            details=details,
            duration_ms=0.0,
            timestamp=datetime.now(),
            recommendations=recommendations
        )
    
    async def _check_disk_space(self) -> HealthCheckResult:
        """Check database disk space usage."""
        details = {}
        recommendations = []
        issues = []
        
        try:
            # Get database size
            db_size_query = "SELECT pg_database_size(current_database())"
            db_size_bytes = await database_manager.execute_read(
                lambda conn, q: conn.fetchval(q), db_size_query
            )
            
            details["database_size_bytes"] = db_size_bytes
            details["database_size_mb"] = round(db_size_bytes / 1024 / 1024, 2)
            details["database_size_gb"] = round(db_size_bytes / 1024 / 1024 / 1024, 2)
            
            # Get table sizes
            table_sizes_query = """
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 10
            """
            
            table_sizes = await database_manager.execute_read(
                lambda conn, q: conn.fetch(q), table_sizes_query
            )
            
            details["largest_tables"] = [
                {
                    "schema": row["schemaname"],
                    "table": row["tablename"],
                    "size": row["size"],
                    "size_bytes": row["size_bytes"]
                }
                for row in table_sizes
            ]
            
            # Get available disk space (this would need OS-level integration in production)
            # For now, we'll use database-level checks
            
            # Check for tables growing too quickly
            large_tables = [
                table for table in details["largest_tables"] 
                if table["size_bytes"] > 100 * 1024 * 1024  # 100MB
            ]
            
            if large_tables:
                recommendations.append("Monitor large table growth")
            
            # Check WAL (Write-Ahead Log) size
            wal_size_query = """
                SELECT COALESCE(SUM(size), 0) as wal_size
                FROM pg_ls_waldir()
            """
            
            try:
                wal_size_bytes = await database_manager.execute_read(
                    lambda conn, q: conn.fetchval(q), wal_size_query
                )
                
                details["wal_size_bytes"] = wal_size_bytes
                details["wal_size_mb"] = round(wal_size_bytes / 1024 / 1024, 2)
                
                # WAL size warning threshold (1GB)
                if wal_size_bytes > 1024 * 1024 * 1024:
                    issues.append(f"Large WAL size: {details['wal_size_mb']}MB")
                    recommendations.append("Consider WAL cleanup or archiving")
                    
            except Exception as e:
                self.logger.warning(f"Could not check WAL size: {str(e)}")
                details["wal_check_error"] = str(e)
            
        except Exception as e:
            issues.append(f"Disk space check failed: {str(e)}")
            recommendations.append("Check database permissions for disk monitoring")
            details["error"] = str(e)
        
        # Determine status based on database size
        if not issues:
            if details.get("database_size_gb", 0) > 10:  # 10GB threshold
                status = HealthStatus.WARNING
                message = f"Large database size: {details.get('database_size_gb', 0)}GB"
                recommendations.append("Monitor database growth and consider archiving")
            else:
                status = HealthStatus.HEALTHY
                message = f"Database size acceptable: {details.get('database_size_gb', 0)}GB"
        else:
            status = HealthStatus.CRITICAL
            message = f"Disk space issues: {'; '.join(issues)}"
        
        return HealthCheckResult(
            check_name="disk_space",
            status=status,
            message=message,
            details=details,
            duration_ms=0.0,
            timestamp=datetime.now(),
            recommendations=recommendations
        )
    
    async def _check_replication_lag(self) -> HealthCheckResult:
        """Check replication lag between primary and replicas."""
        details = {}
        recommendations = []
        issues = []
        
        if not database_manager.replica_nodes:
            return HealthCheckResult(
                check_name="replication_lag",
                status=HealthStatus.HEALTHY,
                message="No replica databases configured",
                details={"replicas_configured": False},
                duration_ms=0.0,
                timestamp=datetime.now(),
                recommendations=[]
            )
        
        details["replicas_configured"] = True
        details["replica_count"] = len(database_manager.replica_nodes)
        details["replica_status"] = []
        
        try:
            # Get current WAL position from primary
            primary_wal_query = "SELECT pg_current_wal_lsn()"
            primary_wal_lsn = await database_manager.execute_write(
                lambda conn, q: conn.fetchval(q), primary_wal_query
            )
            
            details["primary_wal_lsn"] = str(primary_wal_lsn)
            
            # Check each replica
            for i, replica_node in enumerate(database_manager.replica_nodes):
                replica_info = {
                    "replica_index": i,
                    "status": replica_node.state.value
                }
                
                if replica_node.state == DatabaseConnectionState.HEALTHY:
                    try:
                        # Get replica's received WAL position
                        replica_wal_query = "SELECT pg_last_wal_receive_lsn()"
                        replica_wal_lsn = await replica_node.execute_with_retry(
                            lambda conn, q: conn.fetchval(q), replica_wal_query
                        )
                        
                        replica_info["replica_wal_lsn"] = str(replica_wal_lsn) if replica_wal_lsn else "NULL"
                        
                        # Calculate lag (this is simplified - actual lag calculation is more complex)
                        if replica_wal_lsn:
                            lag_query = f"SELECT pg_wal_lsn_diff('{primary_wal_lsn}', '{replica_wal_lsn}')"
                            lag_bytes = await database_manager.execute_read(
                                lambda conn, q: conn.fetchval(q), lag_query
                            )
                            
                            replica_info["lag_bytes"] = lag_bytes
                            replica_info["lag_mb"] = round(lag_bytes / 1024 / 1024, 2) if lag_bytes else 0
                            
                            # Check if lag is too high (10MB threshold)
                            if lag_bytes and lag_bytes > 10 * 1024 * 1024:
                                issues.append(f"Replica {i+1} lag: {replica_info['lag_mb']}MB")
                                recommendations.append(f"Investigate replication lag on replica {i+1}")
                        else:
                            issues.append(f"Replica {i+1} WAL position unavailable")
                            
                    except Exception as e:
                        replica_info["error"] = str(e)
                        issues.append(f"Replica {i+1} check failed: {str(e)}")
                else:
                    issues.append(f"Replica {i+1} is {replica_node.state.value}")
                
                details["replica_status"].append(replica_info)
            
        except Exception as e:
            issues.append(f"Replication lag check failed: {str(e)}")
            recommendations.append("Check replication configuration")
            details["error"] = str(e)
        
        # Determine status
        if not issues:
            status = HealthStatus.HEALTHY
            message = "Replication lag within acceptable limits"
        elif any("lag:" in issue for issue in issues):
            status = HealthStatus.WARNING
            message = f"Replication lag detected: {'; '.join([i for i in issues if 'lag:' in i])}"
        else:
            status = HealthStatus.CRITICAL
            message = f"Replication issues: {'; '.join(issues)}"
        
        return HealthCheckResult(
            check_name="replication_lag",
            status=status,
            message=message,
            details=details,
            duration_ms=0.0,
            timestamp=datetime.now(),
            recommendations=recommendations
        )
    
    async def _check_security_validation(self) -> HealthCheckResult:
        """Check database security configuration."""
        details = {}
        recommendations = []
        issues = []
        
        try:
            # Check for unencrypted sensitive data
            encryption_checks = [
                ("messages", "content_encrypted", "Messages with unencrypted content"),
                ("children", "hashed_identifier", "Children with missing hash identifiers")
            ]
            
            details["encryption_checks"] = []
            
            for table, column, description in encryption_checks:
                if column == "content_encrypted":
                    unencrypted_query = f"""
                        SELECT COUNT(*) FROM {table} 
                        WHERE {column} IS NULL 
                        AND sender_type = 'child'
                        AND is_deleted = false
                    """
                else:
                    unencrypted_query = f"""
                        SELECT COUNT(*) FROM {table} 
                        WHERE {column} IS NULL 
                        AND is_deleted = false
                    """
                
                unencrypted_count = await database_manager.execute_read(
                    lambda conn, q: conn.fetchval(q), unencrypted_query
                )
                
                encryption_check = {
                    "description": description,
                    "unencrypted_count": unencrypted_count,
                    "table": table,
                    "column": column
                }
                
                details["encryption_checks"].append(encryption_check)
                
                if unencrypted_count > 0:
                    issues.append(f"{unencrypted_count} {description.lower()}")
                    recommendations.append(f"Encrypt sensitive data in {table}.{column}")
            
            # Check for weak passwords (length check)
            weak_password_query = """
                SELECT COUNT(*) FROM users 
                WHERE password_hash IS NOT NULL 
                AND LENGTH(password_hash) < 60  -- bcrypt hashes should be ~60 chars
                AND is_deleted = false
            """
            
            weak_password_count = await database_manager.execute_read(
                lambda conn, q: conn.fetchval(q), weak_password_query
            )
            
            details["weak_passwords"] = weak_password_count
            
            if weak_password_count > 0:
                issues.append(f"{weak_password_count} accounts with weak password hashes")
                recommendations.append("Review password hashing implementation")
            
            # Check for missing audit logs
            missing_audit_query = """
                SELECT COUNT(*) FROM users 
                WHERE created_at > NOW() - INTERVAL '7 days'
                AND NOT EXISTS (
                    SELECT 1 FROM audit_logs 
                    WHERE resource_type = 'User' 
                    AND resource_id = users.id
                    AND action = 'create'
                )
            """
            
            missing_audit_count = await database_manager.execute_read(
                lambda conn, q: conn.fetchval(q), missing_audit_query
            )
            
            details["missing_audit_logs"] = missing_audit_count
            
            if missing_audit_count > 0:
                issues.append(f"{missing_audit_count} recent users without audit logs")
                recommendations.append("Ensure audit logging for all user operations")
            
            # Check connection security settings
            ssl_query = "SHOW ssl"
            ssl_enabled = await database_manager.execute_read(
                lambda conn, q: conn.fetchval(q), ssl_query
            )
            
            details["ssl_enabled"] = ssl_enabled
            
            if ssl_enabled != "on":
                issues.append("SSL not enabled for database connections")
                recommendations.append("Enable SSL for database connections")
            
        except Exception as e:
            issues.append(f"Security validation failed: {str(e)}")
            recommendations.append("Check database security configuration")
            details["error"] = str(e)
        
        # Determine status
        if not issues:
            status = HealthStatus.HEALTHY
            message = "Security validation passed"
        elif len(issues) == 1 and "weak password" in issues[0]:
            status = HealthStatus.WARNING
            message = f"Security warnings: {'; '.join(issues)}"
        else:
            status = HealthStatus.CRITICAL
            message = f"Security issues detected: {'; '.join(issues)}"
        
        return HealthCheckResult(
            check_name="security_validation",
            status=status,
            message=message,
            details=details,
            duration_ms=0.0,
            timestamp=datetime.now(),
            recommendations=recommendations
        )
    
    def _determine_overall_health_status(self, results: Dict[str, HealthCheckResult]) -> HealthStatus:
        """Determine overall health status from individual check results."""
        if not results:
            return HealthStatus.UNKNOWN
        
        statuses = [result.status for result in results.values()]
        
        if HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            return HealthStatus.WARNING
        elif all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN


# Global health checker instance
database_health_checker = DatabaseHealthChecker()


# Convenience functions
async def run_database_health_check() -> Dict[str, HealthCheckResult]:
    """Run comprehensive database health check."""
    return await database_health_checker.run_comprehensive_health_check()


async def get_database_health_summary() -> Dict[str, Any]:
    """Get database health summary."""
    health_results = await run_database_health_check()
    
    summary = {
        "timestamp": datetime.now().isoformat(),
        "overall_status": database_health_checker._determine_overall_health_status(health_results).value,
        "total_checks": len(health_results),
        "healthy_checks": len([r for r in health_results.values() if r.status == HealthStatus.HEALTHY]),
        "warning_checks": len([r for r in health_results.values() if r.status == HealthStatus.WARNING]),
        "critical_checks": len([r for r in health_results.values() if r.status == HealthStatus.CRITICAL]),
        "checks": {
            name: {
                "status": result.status.value,
                "message": result.message,
                "duration_ms": result.duration_ms
            }
            for name, result in health_results.items()
        }
    }
    
    return summary
