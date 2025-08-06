#!/usr/bin/env python3
"""
AI Teddy Bear Performance Optimization Tool
===========================================

Comprehensive performance analysis and optimization for the AI Teddy Bear project.

Features:
- Memory usage analysis and optimization
- Threading locks optimization
- Database connection pooling optimization
- File I/O performance optimization
- Code profiling and bottleneck detection
"""

import asyncio
import gc
import logging
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Dict, List, Any
import psutil
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class PerformanceMetrics:
    """Performance metrics container."""

    memory_usage_mb: float
    cpu_usage_percent: float
    active_threads: int
    open_file_descriptors: int
    response_time_ms: float
    database_connections: int
    cache_hit_ratio: float
    error_rate: float


class PerformanceOptimizer:
    """
    Comprehensive performance optimization tool.

    Analyzes and optimizes:
    - Memory management and garbage collection
    - Threading and async operations
    - Database connection pooling
    - File I/O operations
    - Cache efficiency
    """

    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
        self.optimization_results: Dict[str, Any] = {}

    async def run_full_optimization(self) -> Dict[str, Any]:
        """Run complete performance optimization suite."""
        logger.info("🚀 Starting comprehensive performance optimization...")

        # Start memory tracing
        tracemalloc.start()
        start_time = time.time()

        try:
            results = {
                "timestamp": datetime.now().isoformat(),
                "optimization_results": {},
                "recommendations": [],
                "metrics": {},
            }

            # 1. Memory optimization
            logger.info("🧠 Optimizing memory usage...")
            memory_results = await self._optimize_memory_usage()
            results["optimization_results"]["memory"] = memory_results

            # 2. Threading optimization
            logger.info("🔄 Optimizing threading and locks...")
            threading_results = await self._optimize_threading()
            results["optimization_results"]["threading"] = threading_results

            # 3. Database optimization
            logger.info("🗄️ Optimizing database connections...")
            db_results = await self._optimize_database_connections()
            results["optimization_results"]["database"] = db_results

            # 4. File I/O optimization
            logger.info("📁 Optimizing file operations...")
            io_results = await self._optimize_file_operations()
            results["optimization_results"]["file_io"] = io_results

            # 5. Code profiling
            logger.info("⚡ Running code profiling...")
            profiling_results = await self._run_code_profiling()
            results["optimization_results"]["profiling"] = profiling_results

            # 6. Generate recommendations
            logger.info("💡 Generating optimization recommendations...")
            recommendations = self._generate_recommendations(
                results["optimization_results"]
            )
            results["recommendations"] = recommendations

            # Final metrics
            current_metrics = self._collect_current_metrics()
            results["metrics"] = (
                current_metrics._dict__
                if hasattr(current_metrics, "_dict__")
                else str(current_metrics)
            )

            total_time = time.time() - start_time
            results["optimization_duration_seconds"] = total_time

            logger.info(
                f"✅ Performance optimization completed in {total_time:.2f} seconds"
            )
            return results

        except Exception as e:
            logger.error(f"❌ Performance optimization failed: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}
        finally:
            tracemalloc.stop()

    async def _optimize_memory_usage(self) -> Dict[str, Any]:
        """Optimize memory usage and garbage collection."""
        try:
            # Get current memory snapshot
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics("lineno")

            # Force garbage collection
            collected = gc.collect()

            # Memory usage analysis
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()

            # Find memory hotspots
            memory_hotspots = []
            for stat in top_stats[:10]:
                memory_hotspots.append(
                    {
                        "file": (
                            stat.traceback.format()[0]
                            if stat.traceback.format()
                            else "unknown"
                        ),
                        "size_mb": stat.size / (1024 * 1024),
                        "count": stat.count,
                    }
                )

            return {
                "status": "completed",
                "garbage_collected_objects": collected,
                "memory_usage_mb": memory_info.rss / (1024 * 1024),
                "memory_percent": memory_percent,
                "memory_hotspots": memory_hotspots,
                "recommendations": [
                    "Consider implementing memory pooling for frequently created objects",
                    "Review large object allocations in memory hotspots",
                    "Implement lazy loading for large data structures",
                ],
            }

        except Exception as e:
            logger.error(f"Memory optimization failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _optimize_threading(self) -> Dict[str, Any]:
        """Optimize threading and lock usage."""
        try:
            # Analyze current threading
            thread_count = threading.active_count()
            threads = threading.enumerate()

            thread_info = []
            for thread in threads:
                thread_info.append(
                    {
                        "name": thread.name,
                        "daemon": thread.daemon,
                        "alive": thread.is_alive(),
                        "ident": thread.ident,
                    }
                )

            # Check for potential deadlocks (basic analysis)
            potential_issues = []
            if thread_count > 50:
                potential_issues.append(
                    "High thread count detected - consider using asyncio"
                )

            # Analyze asyncio tasks if available
            asyncio_tasks = []
            try:
                # Get all asyncio tasks
                all_tasks = asyncio.all_tasks()
                asyncio_tasks = [
                    {
                        "name": task.get_name(),
                        "done": task.done(),
                        "cancelled": task.cancelled(),
                    }
                    for task in all_tasks
                ]
            except RuntimeError:
                # No asyncio loop running
                pass

            return {
                "status": "completed",
                "thread_count": thread_count,
                "thread_details": thread_info,
                "asyncio_tasks": asyncio_tasks,
                "potential_issues": potential_issues,
                "recommendations": [
                    "Replace threading.Lock with asyncio.Lock where possible",
                    "Use asyncio.gather() for concurrent operations",
                    "Implement connection pooling to reduce thread overhead",
                    "Consider using asyncio.Semaphore for resource limiting",
                ],
            }

        except Exception as e:
            logger.error(f"Threading optimization failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _optimize_database_connections(self) -> Dict[str, Any]:
        """Optimize database connection pooling."""
        try:
            recommendations = []
            analysis = {}

            # Check if database modules are available
            try:
                # Test if module exists
                import importlib.util

                spec = importlib.util.find_spec("src.adapters.database_production")
                if spec is not None:
                    # Module exists
                    analysis["database_adapter_available"] = True
                    recommendations.extend(
                        [
                            "Ensure connection pool size matches expected concurrent users",
                            "Set appropriate connection timeout values",
                            "Implement connection health checks",
                            "Use prepared statements for repeated queries",
                            "Monitor connection pool metrics",
                        ]
                    )
                else:
                    analysis["database_adapter_available"] = False
                    recommendations.append("Database adapter module not found")

            except Exception:
                analysis["database_adapter_available"] = False
                recommendations.append("Database adapter not accessible")

            # Check for connection pool configuration
            pool_config = {
                "recommended_pool_size": min(max(psutil.cpu_count() * 2, 5), 20),
                "recommended_max_overflow": 10,
                "recommended_pool_timeout": 30,
                "recommended_pool_recycle": 3600,
            }
            analysis["recommended_config"] = pool_config

            return {
                "status": "completed",
                "analysis": analysis,
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _optimize_file_operations(self) -> Dict[str, Any]:
        """Optimize file I/O operations."""
        try:
            # Check file descriptor usage
            process = psutil.Process()
            open_files = len(process.open_files())
            max_files = 1024  # Default limit, could be higher

            # Check for large files that might need streaming
            large_files = []
            project_files = Path(PROJECT_ROOT).rglob("*")

            for file_path in project_files:
                if file_path.is_file():
                    try:
                        size = file_path.stat().st_size
                        if size > 10 * 1024 * 1024:  # Files larger than 10MB
                            large_files.append(
                                {
                                    "path": str(file_path),
                                    "size_mb": size / (1024 * 1024),
                                }
                            )
                    except (OSError, PermissionError):
                        continue

            # File I/O recommendations
            recommendations = [
                "Use async file operations for large files",
                "Implement file streaming for uploads/downloads",
                "Cache frequently accessed small files",
                "Use buffered I/O for better performance",
            ]

            if open_files > max_files * 0.8:
                recommendations.append(
                    "High file descriptor usage - check for file leaks"
                )

            return {
                "status": "completed",
                "open_file_descriptors": open_files,
                "large_files_count": len(large_files),
                "large_files": large_files[:5],  # Show top 5
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.error(f"File I/O optimization failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _run_code_profiling(self) -> Dict[str, Any]:
        """Run basic code profiling analysis."""
        try:
            # CPU usage analysis
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()

            # Memory usage analysis
            memory = psutil.virtual_memory()

            # Disk I/O analysis
            disk_io = psutil.disk_io_counters()

            profiling_data = {
                "cpu_usage_percent": cpu_percent,
                "cpu_count": cpu_count,
                "memory_total_gb": memory.total / (1024**3),
                "memory_available_gb": memory.available / (1024**3),
                "memory_percent": memory.percent,
                "disk_read_mb": disk_io.read_bytes / (1024**2) if disk_io else 0,
                "disk_write_mb": disk_io.write_bytes / (1024**2) if disk_io else 0,
            }

            # Performance recommendations based on profiling
            recommendations = []

            if cpu_percent > 80:
                recommendations.append(
                    "High CPU usage detected - consider optimizing computational tasks"
                )

            if memory.percent > 80:
                recommendations.append(
                    "High memory usage detected - review memory allocation"
                )

            if profiling_data["disk_read_mb"] > 1000:
                recommendations.append(
                    "High disk read activity - consider caching strategies"
                )

            return {
                "status": "completed",
                "profiling_data": profiling_data,
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.error(f"Code profiling failed: {e}")
            return {"status": "failed", "error": str(e)}

    def _collect_current_metrics(self) -> PerformanceMetrics:
        """Collect current system performance metrics."""
        try:
            process = psutil.Process()

            return PerformanceMetrics(
                memory_usage_mb=process.memory_info().rss / (1024 * 1024),
                cpu_usage_percent=process.cpu_percent(),
                active_threads=threading.active_count(),
                open_file_descriptors=len(process.open_files()),
                response_time_ms=0.0,  # Would need actual measurement
                database_connections=0,  # Would need database inspection
                cache_hit_ratio=0.0,  # Would need cache metrics
                error_rate=0.0,  # Would need error tracking
            )

        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
            return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0)

    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate comprehensive optimization recommendations."""
        recommendations = []

        # Collect all recommendations from individual optimizations
        for category, result in results.items():
            if isinstance(result, dict) and "recommendations" in result:
                recommendations.extend(result["recommendations"])

        # Add general recommendations
        recommendations.extend(
            [
                "Implement comprehensive monitoring and alerting",
                "Regular performance testing and benchmarking",
                "Use async/await patterns consistently",
                "Implement proper error handling and circuit breakers",
                "Consider implementing microservices for scalability",
                "Use Redis for caching and session management",
                "Implement database query optimization",
                "Use CDN for static content delivery",
                "Implement proper logging and observability",
            ]
        )

        # Remove duplicates and return
        return list(set(recommendations))


@contextmanager
def performance_timer():
    """Context manager for timing operations."""
    start = time.time()
    yield
    end = time.time()
    logger.info(f"Operation completed in {end - start:.3f} seconds")


async def main():
    """Main function to run performance optimization."""
    optimizer = PerformanceOptimizer()

    with performance_timer():
        results = await optimizer.run_full_optimization()

    # Save results to file
    import json

    output_file = PROJECT_ROOT / "performance_optimization_report.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"📊 Performance optimization report saved to: {output_file}")

    # Print summary
    if "optimization_results" in results:
        logger.info("📈 Optimization Summary:")
        for category, result in results["optimization_results"].items():
            status = result.get("status", "unknown")
            logger.info(f"  - {category.title()}: {status}")

    if "recommendations" in results:
        logger.info(
            f"💡 Generated {len(results['recommendations'])} optimization recommendations"
        )


if __name__ == "__main__":
    asyncio.run(main())
