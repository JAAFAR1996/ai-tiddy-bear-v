#!/usr/bin/env python3
"""
Prometheus Metrics Exporter for AI Teddy Bear Backup Services

Exports backup-related metrics to Prometheus for monitoring and alerting
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from prometheus_client import start_http_server, Counter, Histogram, Gauge, Info
from prometheus_client.core import CollectorRegistry
import signal

# Backup service imports
from src.infrastructure.monitoring.prometheus_metrics import PrometheusMetricsCollector


class BackupMetricsExporter:
    """
    Prometheus metrics exporter for backup services
    """

    def __init__(self):
        self.logger = self._setup_logging()
        self.registry = CollectorRegistry()
        self.port = int(os.getenv('PROMETHEUS_PORT', '9090'))
        self.running = False
        
        # Initialize metrics
        self._initialize_metrics()
        
        # Metrics update interval
        self.update_interval = int(os.getenv('METRICS_UPDATE_INTERVAL', '30'))

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)

    def _initialize_metrics(self) -> None:
        """Initialize Prometheus metrics"""
        
        # Backup operation metrics
        self.backup_operations_total = Counter(
            'backup_operations_total',
            'Total number of backup operations',
            ['component', 'type', 'status'],
            registry=self.registry
        )
        
        self.backup_duration_seconds = Histogram(
            'backup_duration_seconds',
            'Duration of backup operations in seconds',
            ['component', 'type'],
            registry=self.registry,
            buckets=[30, 60, 300, 600, 1800, 3600, 7200]  # 30s to 2h
        )
        
        self.backup_size_bytes = Histogram(
            'backup_size_bytes',
            'Size of backup files in bytes',
            ['component', 'type'],
            registry=self.registry,
            buckets=[1e6, 10e6, 100e6, 1e9, 10e9, 100e9]  # 1MB to 100GB
        )
        
        self.backup_throughput_mbps = Gauge(
            'backup_throughput_mbps',
            'Backup throughput in MB per second',
            ['component', 'type'],
            registry=self.registry
        )
        
        # Storage metrics
        self.storage_total_bytes = Gauge(
            'storage_total_bytes',
            'Total storage space in bytes',
            ['provider'],
            registry=self.registry
        )
        
        self.storage_used_bytes = Gauge(
            'storage_used_bytes',
            'Used storage space in bytes',
            ['provider'],
            registry=self.registry
        )
        
        self.storage_usage_percentage = Gauge(
            'storage_usage_percentage',
            'Storage usage percentage',
            ['provider'],
            registry=self.registry
        )
        
        self.storage_backup_count = Gauge(
            'storage_backup_count',
            'Number of backups in storage',
            ['provider'],
            registry=self.registry
        )
        
        # Restore operation metrics
        self.restore_operations_total = Counter(
            'restore_operations_total',
            'Total number of restore operations',
            ['type', 'status'],
            registry=self.registry
        )
        
        self.restore_duration_seconds = Histogram(
            'restore_duration_seconds',
            'Duration of restore operations in seconds',
            ['type'],
            registry=self.registry,
            buckets=[60, 300, 600, 1800, 3600, 7200, 14400]  # 1m to 4h
        )
        
        # Scheduler metrics
        self.scheduled_backup_jobs_total = Counter(
            'scheduled_backup_jobs_total',
            'Total number of scheduled backup jobs',
            ['job_id', 'tier', 'status'],
            registry=self.registry
        )
        
        self.backup_scheduler_queue_size = Gauge(
            'backup_scheduler_queue_size',
            'Number of jobs in backup scheduler queue',
            registry=self.registry
        )
        
        self.backup_scheduler_active_jobs = Gauge(
            'backup_scheduler_active_jobs',
            'Number of active backup jobs',
            registry=self.registry
        )
        
        # Alert metrics
        self.backup_alerts_total = Counter(
            'backup_alerts_total',
            'Total number of backup alerts',
            ['severity', 'component'],
            registry=self.registry
        )
        
        # COPPA compliance metrics
        self.backup_coppa_compliant = Gauge(
            'backup_coppa_compliant',
            'COPPA compliance status for backup (1=compliant, 0=non-compliant)',
            ['backup_id'],
            registry=self.registry
        )
        
        self.coppa_compliance_rate = Gauge(
            'coppa_compliance_rate',
            'Overall COPPA compliance rate',
            registry=self.registry
        )
        
        # SLA metrics
        self.sla_rto_actual_minutes = Gauge(
            'sla_rto_actual_minutes',
            'Actual Recovery Time Objective in minutes',
            registry=self.registry
        )
        
        self.sla_rpo_actual_minutes = Gauge(
            'sla_rpo_actual_minutes',
            'Actual Recovery Point Objective in minutes',
            registry=self.registry
        )
        
        self.sla_rto_breaches_total = Counter(
            'sla_rto_breaches_total',
            'Total number of RTO breaches',
            registry=self.registry
        )
        
        self.sla_rpo_breaches_total = Counter(
            'sla_rpo_breaches_total',
            'Total number of RPO breaches',
            registry=self.registry
        )
        
        # Test metrics
        self.backup_test_executions_total = Counter(
            'backup_test_executions_total',
            'Total number of backup test executions',
            ['status'],
            registry=self.registry
        )
        
        self.backup_test_execution_duration_seconds = Histogram(
            'backup_test_execution_duration_seconds',
            'Duration of backup test executions in seconds',
            registry=self.registry
        )
        
        self.backup_test_cases_total = Counter(
            'backup_test_cases_total',
            'Total number of backup test cases',
            ['type', 'status'],
            registry=self.registry
        )
        
        self.backup_test_success_rate = Histogram(
            'backup_test_success_rate',
            'Success rate of backup tests',
            ['type'],
            registry=self.registry,
            buckets=[0.0, 0.5, 0.8, 0.9, 0.95, 0.99, 1.0]
        )
        
        # System health metrics
        self.backup_service_up = Gauge(
            'backup_service_up',
            'Backup service availability (1=up, 0=down)',
            ['service'],
            registry=self.registry
        )
        
        self.backup_service_last_success_timestamp = Gauge(
            'backup_service_last_success_timestamp',
            'Timestamp of last successful backup',
            ['component'],
            registry=self.registry
        )
        
        # Information metrics
        self.backup_service_info = Info(
            'backup_service_info',
            'Information about backup service',
            registry=self.registry
        )
        
        # Set service info
        self.backup_service_info.info({
            'version': os.getenv('VERSION', 'unknown'),
            'environment': os.getenv('ENVIRONMENT', 'unknown'),
            'backup_encryption_enabled': str(bool(os.getenv('BACKUP_ENCRYPTION_KEY'))),
            'coppa_compliance_mode': os.getenv('COPPA_COMPLIANCE_MODE', 'false')
        })

    async def _update_system_metrics(self) -> None:
        """Update system-level metrics"""
        try:
            # Check if backup services are running
            services = ['orchestrator', 'scheduler', 'monitor']
            
            for service in services:
                # This would check actual service health
                # For now, assume they're up if the exporter is running
                self.backup_service_up.labels(service=service).set(1)
            
            # Update last success timestamps (would read from actual data)
            current_time = time.time()
            for component in ['database', 'files', 'config']:
                # This would read actual last success time from storage
                self.backup_service_last_success_timestamp.labels(
                    component=component
                ).set(current_time - 3600)  # Placeholder: 1 hour ago
            
        except Exception as e:
            self.logger.error(f"Error updating system metrics: {e}")

    async def _update_storage_metrics(self) -> None:
        """Update storage-related metrics"""
        try:
            # This would interface with actual storage backends
            # For now, provide placeholder values
            
            providers = ['local', 's3', 'azure']
            
            for provider in providers:
                # Simulate storage metrics
                total_gb = 1000  # 1TB
                used_gb = 500    # 500GB
                usage_pct = used_gb / total_gb
                backup_count = 150
                
                self.storage_total_bytes.labels(provider=provider).set(total_gb * 1024**3)
                self.storage_used_bytes.labels(provider=provider).set(used_gb * 1024**3)
                self.storage_usage_percentage.labels(provider=provider).set(usage_pct)
                self.storage_backup_count.labels(provider=provider).set(backup_count)
                
        except Exception as e:
            self.logger.error(f"Error updating storage metrics: {e}")

    async def _update_compliance_metrics(self) -> None:
        """Update COPPA compliance metrics"""
        try:
            # Calculate overall compliance rate
            # This would read from actual compliance data
            compliance_rate = 0.98  # 98% compliant (placeholder)
            
            self.coppa_compliance_rate.set(compliance_rate)
            
        except Exception as e:
            self.logger.error(f"Error updating compliance metrics: {e}")

    async def _metrics_update_loop(self) -> None:
        """Main metrics update loop"""
        self.logger.info("Starting metrics update loop")
        
        while self.running:
            try:
                # Update various metric categories
                await self._update_system_metrics()
                await self._update_storage_metrics()
                await self._update_compliance_metrics()
                
                # Wait before next update
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                self.logger.error(f"Error in metrics update loop: {e}")
                await asyncio.sleep(self.update_interval)

    async def start(self) -> None:
        """Start the metrics exporter"""
        self.logger.info(f"Starting Prometheus metrics exporter on port {self.port}")
        
        try:
            # Start the HTTP server for Prometheus
            start_http_server(self.port, registry=self.registry)
            self.logger.info(f"Metrics server started on http://0.0.0.0:{self.port}/metrics")
            
            # Set running flag
            self.running = True
            
            # Start metrics update loop
            await self._metrics_update_loop()
            
        except Exception as e:
            self.logger.error(f"Failed to start metrics exporter: {e}")
            raise

    async def stop(self) -> None:
        """Stop the metrics exporter"""
        self.logger.info("Stopping metrics exporter")
        self.running = False

    def get_registry(self) -> CollectorRegistry:
        """Get the Prometheus registry for external use"""
        return self.registry


def setup_signal_handlers(exporter: BackupMetricsExporter) -> None:
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logging.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(exporter.stop())
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


async def main():
    """Main entry point"""
    # Create metrics exporter
    exporter = BackupMetricsExporter()
    
    # Setup signal handlers
    setup_signal_handlers(exporter)
    
    try:
        # Start the exporter
        await exporter.start()
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
    except Exception as e:
        logging.error(f"Metrics exporter failed: {e}")
        return 1
    finally:
        # Ensure clean shutdown
        await exporter.stop()
    
    return 0


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)