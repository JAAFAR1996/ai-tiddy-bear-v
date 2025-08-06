#!/usr/bin/env python3
"""
AI Teddy Bear - Real-time Performance Monitoring
================================================

Advanced performance monitoring and metrics collection for load testing:
- Real-time system metrics collection
- Application performance monitoring (APM)
- Child safety system performance tracking
- Memory leak detection
- Performance degradation alerts
- Custom metric dashboards
"""

import asyncio
import time
import logging
import json
import statistics
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from collections import deque, defaultdict
import weakref
import gc
import tracemalloc
import sys
import os
import sqlite3
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class SystemMetric:
    """Single system metric measurement."""
    timestamp: float
    metric_name: str
    value: float
    unit: str
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class PerformanceSnapshot:
    """Complete performance snapshot at a point in time."""
    timestamp: float
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_bytes_sent: float
    network_bytes_recv: float
    open_files: int
    threads: int
    connections: int
    
    # Application-specific metrics
    active_sessions: int
    requests_per_second: float
    avg_response_time: float
    error_rate: float
    
    # Child safety metrics
    content_filter_calls_per_sec: float
    safety_check_avg_time: float
    session_isolation_violations: int

class MetricsCollector:
    """Collects and stores performance metrics."""
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.metrics_history: deque = deque(maxlen=max_history)
        self.custom_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.collecting = False
        self.collection_interval = 1.0  # seconds
        
        # Performance baselines
        self.baselines = {
            "cpu_percent": 20.0,
            "memory_mb": 512.0,
            "avg_response_time": 0.2,
            "error_rate": 1.0
        }
        
        # Alerting thresholds
        self.thresholds = {
            "cpu_percent": 80.0,
            "memory_mb": 2048.0,
            "avg_response_time": 1.0,
            "error_rate": 5.0,
            "open_files": 1000
        }
        
        # Initialize system tracking
        self.process = psutil.Process()
        self.initial_net_io = psutil.net_io_counters()
        self.initial_disk_io = psutil.disk_io_counters()
        
        # Memory tracking
        self.memory_tracker = MemoryTracker()
        
    async def start_collection(self, interval: float = 1.0):
        """Start collecting metrics at specified interval."""
        self.collection_interval = interval
        self.collecting = True
        
        logger.info(f"Starting metrics collection at {interval}s intervals")
        
        while self.collecting:
            try:
                snapshot = await self._collect_snapshot()
                self.metrics_history.append(snapshot)
                
                # Check for alerts
                await self._check_alerts(snapshot)
                
                # Memory leak detection
                if len(self.metrics_history) % 60 == 0:  # Every minute
                    await self._check_memory_leaks()
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                await asyncio.sleep(interval)
    
    def stop_collection(self):
        """Stop metrics collection."""
        self.collecting = False
        logger.info("Stopped metrics collection")
    
    async def _collect_snapshot(self) -> PerformanceSnapshot:
        """Collect complete performance snapshot."""
        timestamp = time.time()
        
        # System metrics
        cpu_percent = self.process.cpu_percent()
        memory_info = self.process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        memory_percent = self.process.memory_percent()
        
        # I/O metrics
        try:
            current_net = psutil.net_io_counters()
            current_disk = psutil.disk_io_counters()
            
            net_sent = current_net.bytes_sent - self.initial_net_io.bytes_sent
            net_recv = current_net.bytes_recv - self.initial_net_io.bytes_recv
            
            if current_disk:
                disk_read = (current_disk.read_bytes - self.initial_disk_io.read_bytes) / 1024 / 1024
                disk_write = (current_disk.write_bytes - self.initial_disk_io.write_bytes) / 1024 / 1024
            else:
                disk_read = disk_write = 0
        except (AttributeError, TypeError):
            net_sent = net_recv = disk_read = disk_write = 0
            
        # Process metrics
        try:
            open_files = self.process.num_fds() if hasattr(self.process, 'num_fds') else len(self.process.open_files())
        except:
            open_files = 0
            
        threads = self.process.num_threads()
        
        try:
            connections = len(self.process.connections())
        except:
            connections = 0
        
        # Application metrics (would be collected from actual app)
        active_sessions = self._get_custom_metric("active_sessions", 0)
        requests_per_second = self._get_custom_metric_rate("requests", 60)  # Last minute
        avg_response_time = self._get_custom_metric_avg("response_time", 60)
        error_rate = self._get_custom_metric_rate("errors", 60)
        
        # Child safety metrics
        content_filter_calls_per_sec = self._get_custom_metric_rate("content_filter_calls", 10)
        safety_check_avg_time = self._get_custom_metric_avg("safety_check_time", 30)
        session_isolation_violations = self._get_custom_metric("session_violations", 0)
        
        return PerformanceSnapshot(
            timestamp=timestamp,
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            memory_percent=memory_percent,
            disk_io_read_mb=disk_read,
            disk_io_write_mb=disk_write,
            network_bytes_sent=net_sent,
            network_bytes_recv=net_recv,
            open_files=open_files,
            threads=threads,
            connections=connections,
            active_sessions=active_sessions,
            requests_per_second=requests_per_second,
            avg_response_time=avg_response_time,
            error_rate=error_rate,
            content_filter_calls_per_sec=content_filter_calls_per_sec,
            safety_check_avg_time=safety_check_avg_time,
            session_isolation_violations=session_isolation_violations
        )
    
    def record_custom_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record custom application metric."""
        metric = SystemMetric(
            timestamp=time.time(),
            metric_name=name,
            value=value,
            unit="",
            tags=tags or {}
        )
        self.custom_metrics[name].append(metric)
    
    def _get_custom_metric(self, name: str, default: float = 0.0) -> float:
        """Get latest custom metric value."""
        metrics = self.custom_metrics.get(name)
        if metrics:
            return metrics[-1].value
        return default
    
    def _get_custom_metric_rate(self, name: str, window_seconds: int = 60) -> float:
        """Calculate rate of custom metric over time window."""
        metrics = self.custom_metrics.get(name)
        if not metrics:
            return 0.0
        
        now = time.time()
        cutoff = now - window_seconds
        
        # Count metrics in time window
        count = sum(1 for m in metrics if m.timestamp >= cutoff)
        return count / window_seconds
    
    def _get_custom_metric_avg(self, name: str, window_seconds: int = 60) -> float:
        """Calculate average of custom metric over time window."""
        metrics = self.custom_metrics.get(name)
        if not metrics:
            return 0.0
        
        now = time.time()
        cutoff = now - window_seconds
        
        # Get metrics in time window
        values = [m.value for m in metrics if m.timestamp >= cutoff]
        return statistics.mean(values) if values else 0.0
    
    async def _check_alerts(self, snapshot: PerformanceSnapshot):
        """Check for performance alerts."""
        alerts = []
        
        # CPU alert
        if snapshot.cpu_percent > self.thresholds["cpu_percent"]:
            alerts.append(f"High CPU usage: {snapshot.cpu_percent:.1f}% > {self.thresholds['cpu_percent']}%")
        
        # Memory alert
        if snapshot.memory_mb > self.thresholds["memory_mb"]:
            alerts.append(f"High memory usage: {snapshot.memory_mb:.1f}MB > {self.thresholds['memory_mb']}MB")
        
        # Response time alert
        if snapshot.avg_response_time > self.thresholds["avg_response_time"]:
            alerts.append(f"Slow response time: {snapshot.avg_response_time:.3f}s > {self.thresholds['avg_response_time']}s")
        
        # Error rate alert
        if snapshot.error_rate > self.thresholds["error_rate"]:
            alerts.append(f"High error rate: {snapshot.error_rate:.2f}% > {self.thresholds['error_rate']}%")
        
        # File descriptor alert
        if snapshot.open_files > self.thresholds["open_files"]:
            alerts.append(f"Too many open files: {snapshot.open_files} > {self.thresholds['open_files']}")
        
        # Child safety alerts
        if snapshot.session_isolation_violations > 0:
            alerts.append(f"Session isolation violations detected: {snapshot.session_isolation_violations}")
        
        if snapshot.safety_check_avg_time > 0.1:  # 100ms
            alerts.append(f"Slow safety checks: {snapshot.safety_check_avg_time*1000:.1f}ms > 100ms")
        
        # Log alerts
        for alert in alerts:
            logger.warning(f"PERFORMANCE ALERT: {alert}")
    
    async def _check_memory_leaks(self):
        """Check for memory leaks."""
        if len(self.metrics_history) < 10:
            return
        
        # Check if memory is consistently increasing
        recent_memory = [s.memory_mb for s in list(self.metrics_history)[-10:]]
        
        if len(recent_memory) >= 2:
            # Calculate trend
            x = list(range(len(recent_memory)))
            y = recent_memory
            
            # Simple linear regression
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(x[i] * x[i] for i in range(n))
            
            if n * sum_x2 - sum_x * sum_x != 0:
                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                
                # If memory is increasing by more than 10MB per measurement
                if slope > 10:
                    logger.warning(f"MEMORY LEAK DETECTED: Memory increasing at {slope:.2f}MB per measurement")
                    
                    # Collect detailed memory info
                    await self.memory_tracker.analyze_memory_usage()
    
    def get_performance_summary(self, window_minutes: int = 10) -> Dict[str, Any]:
        """Get performance summary for time window."""
        if not self.metrics_history:
            return {"error": "No metrics available"}
        
        now = time.time()
        cutoff = now - (window_minutes * 60)
        
        # Filter metrics to time window
        window_metrics = [s for s in self.metrics_history if s.timestamp >= cutoff]
        
        if not window_metrics:
            return {"error": f"No metrics in last {window_minutes} minutes"}
        
        # Calculate statistics
        cpu_values = [s.cpu_percent for s in window_metrics]
        memory_values = [s.memory_mb for s in window_metrics]
        response_time_values = [s.avg_response_time for s in window_metrics if s.avg_response_time > 0]
        rps_values = [s.requests_per_second for s in window_metrics if s.requests_per_second > 0]
        
        summary = {
            "time_window_minutes": window_minutes,
            "total_snapshots": len(window_metrics),
            "cpu": {
                "avg": statistics.mean(cpu_values),
                "max": max(cpu_values),
                "min": min(cpu_values)
            } if cpu_values else {},
            "memory": {
                "avg_mb": statistics.mean(memory_values),
                "max_mb": max(memory_values),
                "min_mb": min(memory_values)
            } if memory_values else {},
            "response_time": {
                "avg_ms": statistics.mean(response_time_values) * 1000,
                "max_ms": max(response_time_values) * 1000,
                "min_ms": min(response_time_values) * 1000
            } if response_time_values else {},
            "throughput": {
                "avg_rps": statistics.mean(rps_values),
                "max_rps": max(rps_values)
            } if rps_values else {},
            "latest": asdict(window_metrics[-1])
        }
        
        return summary
    
    def export_metrics(self, filename: str):
        """Export metrics to file."""
        data = {
            "export_timestamp": datetime.now().isoformat(),
            "total_snapshots": len(self.metrics_history),
            "metrics": [asdict(s) for s in self.metrics_history],
            "custom_metrics": {
                name: [asdict(m) for m in metrics]
                for name, metrics in self.custom_metrics.items()
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Exported {len(self.metrics_history)} metrics snapshots to {filename}")

class MemoryTracker:
    """Advanced memory tracking and leak detection."""
    
    def __init__(self):
        # Start memory tracing
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        
        self.memory_snapshots = []
        self.object_counts = defaultdict(int)
        
    async def analyze_memory_usage(self):
        """Analyze current memory usage."""
        # Take memory snapshot
        snapshot = tracemalloc.take_snapshot()
        self.memory_snapshots.append(snapshot)
        
        # Analyze top memory consumers
        top_stats = snapshot.statistics('lineno')
        
        logger.info("Top 10 memory consumers:")
        for index, stat in enumerate(top_stats[:10], 1):
            logger.info(f"{index}. {stat}")
        
        # Count objects by type
        for obj in gc.get_objects():
            obj_type = type(obj).__name__
            self.object_counts[obj_type] += 1
        
        # Log object counts for common types
        common_types = ['dict', 'list', 'tuple', 'str', 'int', 'function']
        for obj_type in common_types:
            count = self.object_counts.get(obj_type, 0)
            if count > 0:
                logger.info(f"Objects of type {obj_type}: {count}")
        
        # Check for growth
        if len(self.memory_snapshots) >= 2:
            await self._compare_snapshots()
    
    async def _compare_snapshots(self):
        """Compare memory snapshots to detect leaks."""
        if len(self.memory_snapshots) < 2:
            return
        
        current = self.memory_snapshots[-1]
        previous = self.memory_snapshots[-2]
        
        # Compare snapshots
        top_stats = current.compare_to(previous, 'lineno')
        
        logger.info("Memory growth since last snapshot:")
        for stat in top_stats[:5]:
            if stat.size_diff > 1024:  # Only show significant growth (>1KB)
                logger.info(f"  {stat}")

class PerformanceDashboard:
    """Simple text-based performance dashboard."""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.collector = metrics_collector
        self.dashboard_running = False
        
    async def start_dashboard(self, refresh_interval: float = 5.0):
        """Start real-time dashboard."""
        self.dashboard_running = True
        
        while self.dashboard_running:
            try:
                os.system('clear' if os.name == 'posix' else 'cls')  # Clear screen
                
                print("="*80)
                print("AI TEDDY BEAR - REAL-TIME PERFORMANCE DASHBOARD")
                print("="*80)
                print(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print()
                
                # Get latest snapshot
                if self.collector.metrics_history:
                    latest = self.collector.metrics_history[-1]
                    
                    # System metrics
                    print("SYSTEM METRICS")
                    print("-" * 40)
                    print(f"CPU Usage:    {latest.cpu_percent:6.1f}%")
                    print(f"Memory:       {latest.memory_mb:6.1f} MB ({latest.memory_percent:.1f}%)")
                    print(f"Open Files:   {latest.open_files:6d}")
                    print(f"Threads:      {latest.threads:6d}")
                    print(f"Connections:  {latest.connections:6d}")
                    print()
                    
                    # Application metrics
                    print("APPLICATION METRICS")
                    print("-" * 40)
                    print(f"Active Sessions:  {latest.active_sessions:6d}")
                    print(f"Requests/sec:     {latest.requests_per_second:6.1f}")
                    print(f"Avg Response:     {latest.avg_response_time*1000:6.1f} ms")
                    print(f"Error Rate:       {latest.error_rate:6.2f}%")
                    print()
                    
                    # Child safety metrics
                    print("CHILD SAFETY METRICS")
                    print("-" * 40)
                    print(f"Content Filters/sec:  {latest.content_filter_calls_per_sec:6.1f}")
                    print(f"Safety Check Time:    {latest.safety_check_avg_time*1000:6.1f} ms")
                    print(f"Isolation Violations: {latest.session_isolation_violations:6d}")
                    print()
                    
                    # Performance summary
                    summary = self.collector.get_performance_summary(5)  # Last 5 minutes
                    if "error" not in summary:
                        print("5-MINUTE SUMMARY")
                        print("-" * 40)
                        if summary.get("cpu"):
                            print(f"CPU Avg/Max:      {summary['cpu']['avg']:5.1f}% / {summary['cpu']['max']:5.1f}%")
                        if summary.get("memory"):
                            print(f"Memory Avg/Max:   {summary['memory']['avg_mb']:5.1f} / {summary['memory']['max_mb']:5.1f} MB")
                        if summary.get("response_time"):
                            print(f"Response Avg/Max: {summary['response_time']['avg_ms']:5.1f} / {summary['response_time']['max_ms']:5.1f} ms")
                        print()
                    
                    # Status indicators
                    print("STATUS INDICATORS")
                    print("-" * 40)
                    
                    status_items = [
                        ("CPU", latest.cpu_percent < 80, f"{latest.cpu_percent:.1f}%"),
                        ("Memory", latest.memory_mb < 1024, f"{latest.memory_mb:.0f}MB"),
                        ("Response Time", latest.avg_response_time < 0.5, f"{latest.avg_response_time*1000:.0f}ms"),
                        ("Error Rate", latest.error_rate < 5, f"{latest.error_rate:.1f}%"),
                        ("Child Safety", latest.session_isolation_violations == 0, "OK" if latest.session_isolation_violations == 0 else "VIOLATIONS")
                    ]
                    
                    for name, is_healthy, value in status_items:
                        status = "✅" if is_healthy else "❌"
                        print(f"{status} {name:<15} {value}")
                    
                else:
                    print("No metrics available yet...")
                
                print("\nPress Ctrl+C to stop dashboard")
                
                await asyncio.sleep(refresh_interval)
                
            except KeyboardInterrupt:
                self.dashboard_running = False
                break
            except Exception as e:
                logger.error(f"Dashboard error: {e}")
                await asyncio.sleep(refresh_interval)
    
    def stop_dashboard(self):
        """Stop dashboard."""
        self.dashboard_running = False

class LoadTestMonitor:
    """Monitor performance during load testing."""
    
    def __init__(self):
        self.collector = MetricsCollector()
        self.dashboard = PerformanceDashboard(self.collector)
        self.monitoring_tasks = []
        
    async def start_monitoring(self, show_dashboard: bool = False):
        """Start comprehensive monitoring."""
        logger.info("Starting load test monitoring")
        
        # Start metrics collection
        collection_task = asyncio.create_task(self.collector.start_collection(1.0))
        self.monitoring_tasks.append(collection_task)
        
        # Start dashboard if requested
        if show_dashboard:
            dashboard_task = asyncio.create_task(self.dashboard.start_dashboard(3.0))
            self.monitoring_tasks.append(dashboard_task)
        
        return self.monitoring_tasks
    
    async def stop_monitoring(self):
        """Stop all monitoring."""
        logger.info("Stopping load test monitoring")
        
        self.collector.stop_collection()
        self.dashboard.stop_dashboard()
        
        # Cancel all tasks
        for task in self.monitoring_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.monitoring_tasks.clear()
    
    def simulate_application_metrics(self):
        """Simulate application metrics for testing."""
        # Simulate various application events
        self.collector.record_custom_metric("requests", 1)
        self.collector.record_custom_metric("response_time", random.uniform(0.1, 0.5))
        self.collector.record_custom_metric("active_sessions", random.randint(50, 200))
        
        # Simulate errors occasionally
        if random.random() < 0.05:  # 5% chance
            self.collector.record_custom_metric("errors", 1)
        
        # Simulate child safety metrics
        self.collector.record_custom_metric("content_filter_calls", 1)
        self.collector.record_custom_metric("safety_check_time", random.uniform(0.01, 0.05))
        
        # Simulate violations rarely
        if random.random() < 0.01:  # 1% chance
            self.collector.record_custom_metric("session_violations", 1)
    
    def get_monitoring_report(self) -> Dict[str, Any]:
        """Get comprehensive monitoring report."""
        report = {
            "monitoring_summary": {
                "collection_duration_seconds": 0,
                "total_snapshots": len(self.collector.metrics_history),
                "collection_start": None,
                "collection_end": None
            },
            "performance_summary": self.collector.get_performance_summary(60),  # Last hour
            "memory_analysis": {},
            "recommendations": []
        }
        
        if self.collector.metrics_history:
            first_snapshot = self.collector.metrics_history[0]
            last_snapshot = self.collector.metrics_history[-1]
            
            report["monitoring_summary"]["collection_start"] = datetime.fromtimestamp(first_snapshot.timestamp).isoformat()
            report["monitoring_summary"]["collection_end"] = datetime.fromtimestamp(last_snapshot.timestamp).isoformat()
            report["monitoring_summary"]["collection_duration_seconds"] = last_snapshot.timestamp - first_snapshot.timestamp
        
        # Generate recommendations
        summary = report["performance_summary"]
        if "error" not in summary:
            if summary.get("cpu", {}).get("max", 0) > 80:
                report["recommendations"].append("High CPU usage detected - consider scaling or optimization")
            
            if summary.get("memory", {}).get("max_mb", 0) > 1024:
                report["recommendations"].append("High memory usage - monitor for memory leaks")
            
            if summary.get("response_time", {}).get("avg_ms", 0) > 500:
                report["recommendations"].append("Slow response times - investigate performance bottlenecks")
            
            if summary.get("response_time", {}).get("max_ms", 0) > 2000:
                report["recommendations"].append("Very slow maximum response time - check for blocking operations")
        
        return report

# Demo/Test function
async def demo_performance_monitoring():
    """Demonstrate performance monitoring capabilities."""
    monitor = LoadTestMonitor()
    
    try:
        # Start monitoring
        tasks = await monitor.start_monitoring(show_dashboard=False)  # Set to True to see dashboard
        
        logger.info("Performance monitoring started - running for 30 seconds")
        
        # Simulate application activity
        for i in range(30):
            monitor.simulate_application_metrics()
            await asyncio.sleep(1)
        
        # Get report
        report = monitor.get_monitoring_report()
        
        # Save report
        report_file = f"performance_monitoring_demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Performance monitoring report saved to: {report_file}")
        
        # Export detailed metrics
        metrics_file = f"detailed_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        monitor.collector.export_metrics(metrics_file)
        
        print("\nPerformance Monitoring Summary:")
        print("="*50)
        summary = report["performance_summary"]
        if "error" not in summary:
            print(f"Monitoring Duration: {report['monitoring_summary']['collection_duration_seconds']:.1f}s")
            print(f"Total Snapshots: {report['monitoring_summary']['total_snapshots']}")
            
            if summary.get("cpu"):
                print(f"CPU Usage - Avg: {summary['cpu']['avg']:.1f}%, Max: {summary['cpu']['max']:.1f}%")
            
            if summary.get("memory"):
                print(f"Memory Usage - Avg: {summary['memory']['avg_mb']:.1f}MB, Max: {summary['memory']['max_mb']:.1f}MB")
            
            if summary.get("response_time"):
                print(f"Response Time - Avg: {summary['response_time']['avg_ms']:.1f}ms, Max: {summary['response_time']['max_ms']:.1f}ms")
        
        print("\nRecommendations:")
        for rec in report["recommendations"]:
            print(f"• {rec}")
        
        return report
        
    finally:
        await monitor.stop_monitoring()

if __name__ == "__main__":
    import random
    asyncio.run(demo_performance_monitoring())