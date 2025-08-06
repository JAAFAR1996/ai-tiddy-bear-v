"""
Log Aggregation - ELK Stack and CloudWatch Integration
====================================================
Advanced log aggregation and analysis for AI Teddy Bear system:
- ELK Stack (Elasticsearch, Logstash, Kibana) setup and configuration
- CloudWatch Logs integration with custom metrics
- Log parsing and enrichment
- Real-time log analysis and alerting
- Log retention and archival policies
- Performance optimization for log ingestion
"""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

try:
    from elasticsearch import Elasticsearch, helpers
    from elasticsearch.exceptions import ElasticsearchException
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False

from .structured_logger import StructuredLogger, LogLevel, LogCategory, get_logger


class LogDestination(Enum):
    """Log destination types."""
    ELASTICSEARCH = "elasticsearch"
    CLOUDWATCH = "cloudwatch"
    FILE = "file"
    STDOUT = "stdout"


class LogAggregationConfig:
    """Configuration for log aggregation."""
    
    def __init__(self):
        # Elasticsearch configuration
        self.elasticsearch_hosts = self._parse_hosts(os.getenv("ELASTICSEARCH_HOSTS", ""))
        self.elasticsearch_username = os.getenv("ELASTICSEARCH_USERNAME")
        self.elasticsearch_password = os.getenv("ELASTICSEARCH_PASSWORD")
        self.elasticsearch_index_prefix = os.getenv("ELASTICSEARCH_INDEX", "ai-teddy-bear")
        self.elasticsearch_timeout = int(os.getenv("ELASTICSEARCH_TIMEOUT", "30"))
        
        # CloudWatch configuration
        self.cloudwatch_log_group = os.getenv("CLOUDWATCH_LOG_GROUP")
        self.cloudwatch_region = os.getenv("AWS_REGION", "us-east-1")
        self.cloudwatch_retention_days = int(os.getenv("CLOUDWATCH_RETENTION_DAYS", "30"))
        
        # General configuration
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.batch_size = int(os.getenv("LOG_BATCH_SIZE", "100"))
        self.flush_interval = int(os.getenv("LOG_FLUSH_INTERVAL", "5"))
        self.max_queue_size = int(os.getenv("LOG_MAX_QUEUE_SIZE", "10000"))
        
        # Retention configuration
        self.log_retention_days = int(os.getenv("LOG_RETENTION_DAYS", "90"))
        self.archive_after_days = int(os.getenv("LOG_ARCHIVE_DAYS", "30"))
    
    def _parse_hosts(self, hosts_str: str) -> List[str]:
        """Parse Elasticsearch hosts string."""
        if not hosts_str:
            return []
        return [host.strip() for host in hosts_str.split(',')]


@dataclass
class LogMetrics:
    """Log aggregation metrics."""
    total_logs_processed: int = 0
    logs_by_destination: Dict[str, int] = None
    logs_by_level: Dict[str, int] = None
    logs_by_category: Dict[str, int] = None
    errors_count: int = 0
    processing_time_ms: float = 0.0
    queue_size: int = 0
    last_processed: Optional[str] = None
    
    def __post_init__(self):
        if self.logs_by_destination is None:
            self.logs_by_destination = {}
        if self.logs_by_level is None:
            self.logs_by_level = {}
        if self.logs_by_category is None:
            self.logs_by_category = {}


class ElasticsearchAggregator:
    """Elasticsearch log aggregation handler."""
    
    def __init__(self, config: LogAggregationConfig):
        self.config = config
        self.client = None
        self.logger = get_logger("elasticsearch_aggregator")
        
        if ELASTICSEARCH_AVAILABLE and config.elasticsearch_hosts:
            self._setup_client()
    
    def _setup_client(self):
        """Setup Elasticsearch client."""
        try:
            auth = None
            if self.config.elasticsearch_username and self.config.elasticsearch_password:
                auth = (self.config.elasticsearch_username, self.config.elasticsearch_password)
            
            self.client = Elasticsearch(
                hosts=self.config.elasticsearch_hosts,
                http_auth=auth,
                verify_certs=True,
                use_ssl=True,
                timeout=self.config.elasticsearch_timeout,
                max_retries=3,
                retry_on_timeout=True
            )
            
            # Test connection
            if self.client.ping():
                self.logger.info("Elasticsearch connection established")
                self._setup_index_templates()
            else:
                self.logger.error("Elasticsearch connection failed")
                self.client = None
                
        except Exception as e:
            self.logger.error(f"Failed to setup Elasticsearch client: {str(e)}")
            self.client = None
    
    def _setup_index_templates(self):
        """Setup Elasticsearch index templates."""
        template_name = f"{self.config.elasticsearch_index_prefix}-template"
        
        template = {
            "index_patterns": [f"{self.config.elasticsearch_index_prefix}-*"],
            "template": {
                "settings": {
                    "number_of_shards": 2,
                    "number_of_replicas": 1,
                    "index": {
                        "lifecycle": {
                            "name": f"{self.config.elasticsearch_index_prefix}-policy",
                            "rollover_alias": self.config.elasticsearch_index_prefix
                        }
                    },
                    "analysis": {
                        "analyzer": {
                            "message_analyzer": {
                                "type": "standard",
                                "stopwords": "_english_"
                            }
                        }
                    }
                },
                "mappings": {
                    "properties": {
                        "timestamp": {
                            "type": "date",
                            "format": "strict_date_optional_time||epoch_millis"
                        },
                        "level": {"type": "keyword"},
                        "category": {"type": "keyword"},
                        "logger_name": {"type": "keyword"},
                        "message": {
                            "type": "text",
                            "analyzer": "message_analyzer",
                            "fields": {
                                "keyword": {"type": "keyword", "ignore_above": 256}
                            }
                        },
                        "context": {
                            "properties": {
                                "correlation_id": {"type": "keyword"},
                                "trace_id": {"type": "keyword"},
                                "user_id": {"type": "keyword"},
                                "child_id": {"type": "keyword"},
                                "parent_id": {"type": "keyword"},
                                "session_id": {"type": "keyword"},
                                "operation": {"type": "keyword"},
                                "component": {"type": "keyword"},
                                "environment": {"type": "keyword"},
                                "region": {"type": "keyword"}
                            }
                        },
                        "metadata": {"type": "object", "enabled": False},
                        "duration_ms": {"type": "float"},
                        "error_details": {
                            "properties": {
                                "type": {"type": "keyword"},
                                "message": {"type": "text"},
                                "traceback": {"type": "text"}
                            }
                        },
                        "performance_metrics": {"type": "object"},
                        "child_safety_flags": {"type": "object"},
                        "compliance_tags": {"type": "keyword"}
                    }
                }
            }
        }
        
        try:
            self.client.indices.put_index_template(name=template_name, body=template)
            self.logger.info(f"Index template '{template_name}' created/updated")
        except Exception as e:
            self.logger.error(f"Failed to create index template: {str(e)}")
    
    async def send_logs(self, logs: List[Dict[str, Any]]) -> bool:
        """Send logs to Elasticsearch in bulk."""
        if not self.client or not logs:
            return False
        
        try:
            # Prepare documents for bulk insert
            docs = []
            current_date = datetime.now().strftime('%Y.%m.%d')
            index_name = f"{self.config.elasticsearch_index_prefix}-{current_date}"
            
            for log in logs:
                doc = {
                    "_index": index_name,
                    "_source": log
                }
                docs.append(doc)
            
            # Bulk insert
            success_count, failed_items = helpers.bulk(
                self.client,
                docs,
                chunk_size=self.config.batch_size,
                request_timeout=self.config.elasticsearch_timeout
            )
            
            if failed_items:
                self.logger.warning(f"Failed to index {len(failed_items)} documents")
            
            self.logger.debug(f"Successfully indexed {success_count} documents to {index_name}")
            return True
            
        except ElasticsearchException as e:
            self.logger.error(f"Elasticsearch bulk insert failed: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error in Elasticsearch bulk insert: {str(e)}")
            return False
    
    async def create_dashboard(self):
        """Create Kibana dashboard for log analysis."""
        # This would typically create Kibana visualizations and dashboards
        # For now, we'll log the dashboard configuration
        dashboard_config = {
            "version": "7.0.0",
            "objects": [
                {
                    "id": "ai-teddy-bear-logs-overview",
                    "type": "dashboard",
                    "attributes": {
                        "title": "AI Teddy Bear - Logs Overview",
                        "hits": 0,
                        "description": "Overview of application logs",
                        "panelsJSON": json.dumps([
                            {
                                "version": "7.0.0",
                                "gridData": {"x": 0, "y": 0, "w": 24, "h": 15},
                                "panelIndex": "1",
                                "embeddableConfig": {},
                                "panelRefName": "panel_1"
                            }
                        ])
                    }
                }
            ]
        }
        
        self.logger.info("Kibana dashboard configuration prepared", metadata={"config": dashboard_config})


class CloudWatchAggregator:
    """CloudWatch Logs aggregation handler."""
    
    def __init__(self, config: LogAggregationConfig):
        self.config = config
        self.client = None
        self.logger = get_logger("cloudwatch_aggregator")
        self.sequence_tokens = {}
        
        if BOTO3_AVAILABLE and config.cloudwatch_log_group:
            self._setup_client()
    
    def _setup_client(self):
        """Setup CloudWatch Logs client."""
        try:
            self.client = boto3.client('logs', region_name=self.config.cloudwatch_region)
            
            # Test connection
            self.client.describe_log_groups(limit=1)
            self.logger.info("CloudWatch Logs connection established")
            
            # Setup log group and streams
            self._setup_log_group()
            
        except Exception as e:
            self.logger.error(f"Failed to setup CloudWatch client: {str(e)}")
            self.client = None
    
    def _setup_log_group(self):
        """Setup CloudWatch log group and retention policy."""
        try:
            # Check if log group exists
            try:
                self.client.describe_log_groups(
                    logGroupNamePrefix=self.config.cloudwatch_log_group
                )
            except ClientError:
                # Create log group
                self.client.create_log_group(
                    logGroupName=self.config.cloudwatch_log_group
                )
                self.logger.info(f"Created log group: {self.config.cloudwatch_log_group}")
            
            # Set retention policy
            self.client.put_retention_policy(
                logGroupName=self.config.cloudwatch_log_group,
                retentionInDays=self.config.cloudwatch_retention_days
            )
            
        except Exception as e:
            self.logger.error(f"Failed to setup log group: {str(e)}")
    
    def _ensure_log_stream(self, stream_name: str):
        """Ensure log stream exists."""
        if stream_name in self.sequence_tokens:
            return
        
        try:
            # Check if stream exists
            response = self.client.describe_log_streams(
                logGroupName=self.config.cloudwatch_log_group,
                logStreamNamePrefix=stream_name
            )
            
            streams = response.get('logStreams', [])
            if streams:
                # Stream exists, store sequence token
                self.sequence_tokens[stream_name] = streams[0].get('uploadSequenceToken')
            else:
                # Create stream
                self.client.create_log_stream(
                    logGroupName=self.config.cloudwatch_log_group,
                    logStreamName=stream_name
                )
                self.sequence_tokens[stream_name] = None
                
        except Exception as e:
            self.logger.error(f"Failed to ensure log stream {stream_name}: {str(e)}")
    
    async def send_logs(self, logs: List[Dict[str, Any]]) -> bool:
        """Send logs to CloudWatch Logs."""
        if not self.client or not logs:
            return False
        
        try:
            # Group logs by stream (category-based)
            streams = {}
            for log in logs:
                category = log.get('category', 'application')
                stream_name = f"ai-teddy-bear-{category}"
                
                if stream_name not in streams:
                    streams[stream_name] = []
                
                # Convert log to CloudWatch format
                log_event = {
                    'timestamp': int(datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00')).timestamp() * 1000),
                    'message': json.dumps(log)
                }
                streams[stream_name].append(log_event)
            
            # Send logs for each stream
            for stream_name, events in streams.items():
                self._ensure_log_stream(stream_name)
                
                # Sort events by timestamp
                events.sort(key=lambda x: x['timestamp'])
                
                # Send in batches
                for i in range(0, len(events), self.config.batch_size):
                    batch = events[i:i + self.config.batch_size]
                    
                    kwargs = {
                        'logGroupName': self.config.cloudwatch_log_group,
                        'logStreamName': stream_name,
                        'logEvents': batch
                    }
                    
                    if self.sequence_tokens.get(stream_name):
                        kwargs['sequenceToken'] = self.sequence_tokens[stream_name]
                    
                    response = self.client.put_log_events(**kwargs)
                    self.sequence_tokens[stream_name] = response.get('nextSequenceToken')
            
            self.logger.debug(f"Successfully sent {len(logs)} logs to CloudWatch")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send logs to CloudWatch: {str(e)}")
            return False
    
    async def create_metric_filters(self):
        """Create CloudWatch metric filters for log analysis."""
        metric_filters = [
            {
                'filterName': 'ErrorCount',
                'filterPattern': '[timestamp, level="ERROR", ...]',
                'metricTransformations': [
                    {
                        'metricName': 'ErrorCount',
                        'metricNamespace': 'AITeddyBear/Logs',
                        'metricValue': '1'
                    }
                ]
            },
            {
                'filterName': 'ChildSafetyEvents',
                'filterPattern': '[timestamp, level, category="child_safety", ...]',
                'metricTransformations': [
                    {
                        'metricName': 'ChildSafetyEvents',
                        'metricNamespace': 'AITeddyBear/Logs',
                        'metricValue': '1'
                    }
                ]
            },
            {
                'filterName': 'SecurityEvents',
                'filterPattern': '[timestamp, level, category="security", ...]',
                'metricTransformations': [
                    {
                        'metricName': 'SecurityEvents',
                        'metricNamespace': 'AITeddyBear/Logs',
                        'metricValue': '1'
                    }
                ]
            }
        ]
        
        for filter_config in metric_filters:
            try:
                self.client.put_metric_filter(
                    logGroupName=self.config.cloudwatch_log_group,
                    **filter_config
                )
                self.logger.info(f"Created metric filter: {filter_config['filterName']}")
            except Exception as e:
                self.logger.error(f"Failed to create metric filter {filter_config['filterName']}: {str(e)}")


class LogAggregationManager:
    """Main log aggregation manager."""
    
    def __init__(self, config: Optional[LogAggregationConfig] = None):
        self.config = config or LogAggregationConfig()
        self.logger = get_logger("log_aggregation_manager")
        
        # Initialize aggregators
        self.elasticsearch_aggregator = ElasticsearchAggregator(self.config)
        self.cloudwatch_aggregator = CloudWatchAggregator(self.config)
        
        # Log queue and processing
        self.log_queue = asyncio.Queue(maxsize=self.config.max_queue_size)
        self.metrics = LogMetrics()
        
        # Background tasks
        self._processing_task = None
        self._metrics_task = None
        self._cleanup_task = None
    
    async def start(self):
        """Start log aggregation services."""
        try:
            # Start background tasks
            self._processing_task = asyncio.create_task(self._process_logs())
            self._metrics_task = asyncio.create_task(self._collect_metrics())
            self._cleanup_task = asyncio.create_task(self._cleanup_old_logs())
            
            # Setup dashboards and metric filters
            await self._setup_monitoring()
            
            self.logger.info(
                "Log aggregation manager started",
                metadata={
                    "elasticsearch_enabled": self.elasticsearch_aggregator.client is not None,
                    "cloudwatch_enabled": self.cloudwatch_aggregator.client is not None,
                    "batch_size": self.config.batch_size,
                    "flush_interval": self.config.flush_interval
                }
            )
            
        except Exception as e:
            self.logger.error("Failed to start log aggregation manager", error=e)
            raise
    
    async def stop(self):
        """Stop log aggregation services."""
        try:
            # Cancel background tasks
            if self._processing_task:
                self._processing_task.cancel()
            if self._metrics_task:
                self._metrics_task.cancel()
            if self._cleanup_task:
                self._cleanup_task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(
                self._processing_task,
                self._metrics_task,
                self._cleanup_task,
                return_exceptions=True
            )
            
            # Process remaining logs
            await self._flush_queue()
            
            self.logger.info("Log aggregation manager stopped")
            
        except Exception as e:
            self.logger.error("Error stopping log aggregation manager", error=e)
    
    async def add_log(self, log_data: Dict[str, Any]):
        """Add log to processing queue."""
        try:
            if self.log_queue.full():
                self.logger.warning("Log queue is full, dropping log")
                return
            
            await self.log_queue.put(log_data)
            self.metrics.queue_size = self.log_queue.qsize()
            
        except Exception as e:
            self.logger.error("Failed to add log to queue", error=e)
    
    async def _process_logs(self):
        """Background task to process logs."""
        batch = []
        last_flush = time.time()
        
        while True:
            try:
                # Wait for logs or timeout
                try:
                    log_data = await asyncio.wait_for(
                        self.log_queue.get(),
                        timeout=1.0
                    )
                    batch.append(log_data)
                except asyncio.TimeoutError:
                    pass
                
                # Flush if batch is full or timeout reached
                current_time = time.time()
                should_flush = (
                    len(batch) >= self.config.batch_size or
                    (batch and current_time - last_flush >= self.config.flush_interval)
                )
                
                if should_flush and batch:
                    await self._flush_batch(batch)
                    batch.clear()
                    last_flush = current_time
                
            except asyncio.CancelledError:
                # Process remaining logs before exit
                if batch:
                    await self._flush_batch(batch)
                break
            except Exception as e:
                self.logger.error("Error processing logs", error=e)
    
    async def _flush_batch(self, batch: List[Dict[str, Any]]):
        """Flush a batch of logs to all destinations."""
        start_time = time.time()
        
        try:
            # Send to Elasticsearch
            if self.elasticsearch_aggregator.client:
                es_success = await self.elasticsearch_aggregator.send_logs(batch)
                if es_success:
                    self.metrics.logs_by_destination["elasticsearch"] = \
                        self.metrics.logs_by_destination.get("elasticsearch", 0) + len(batch)
            
            # Send to CloudWatch
            if self.cloudwatch_aggregator.client:
                cw_success = await self.cloudwatch_aggregator.send_logs(batch)
                if cw_success:
                    self.metrics.logs_by_destination["cloudwatch"] = \
                        self.metrics.logs_by_destination.get("cloudwatch", 0) + len(batch)
            
            # Update metrics
            self.metrics.total_logs_processed += len(batch)
            self.metrics.processing_time_ms = (time.time() - start_time) * 1000
            self.metrics.last_processed = datetime.now().isoformat()
            
            # Update level and category counts
            for log in batch:
                level = log.get('level', 'UNKNOWN')
                category = log.get('category', 'unknown')
                
                self.metrics.logs_by_level[level] = \
                    self.metrics.logs_by_level.get(level, 0) + 1
                self.metrics.logs_by_category[category] = \
                    self.metrics.logs_by_category.get(category, 0) + 1
            
            self.metrics.queue_size = self.log_queue.qsize()
            
        except Exception as e:
            self.logger.error("Failed to flush log batch", error=e)
            self.metrics.errors_count += 1
    
    async def _flush_queue(self):
        """Flush all remaining logs in queue."""
        remaining_logs = []
        
        while not self.log_queue.empty():
            try:
                log_data = await self.log_queue.get()
                remaining_logs.append(log_data)
            except:
                break
        
        if remaining_logs:
            await self._flush_batch(remaining_logs)
    
    async def _collect_metrics(self):
        """Collect and log metrics periodically."""
        while True:
            try:
                await asyncio.sleep(60)  # Collect every minute
                
                self.logger.info(
                    "Log aggregation metrics",
                    category=LogCategory.PERFORMANCE,
                    performance_metrics=asdict(self.metrics)
                )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error collecting metrics", error=e)
    
    async def _cleanup_old_logs(self):
        """Clean up old logs periodically."""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                
                # This would typically clean up old log indices/streams
                # For now, just log the cleanup attempt
                self.logger.info(
                    "Log cleanup check completed",
                    metadata={
                        "retention_days": self.config.log_retention_days,
                        "archive_days": self.config.archive_after_days
                    }
                )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error during log cleanup", error=e)
    
    async def _setup_monitoring(self):
        """Setup monitoring dashboards and alerts."""
        try:
            # Setup Elasticsearch dashboards
            if self.elasticsearch_aggregator.client:
                await self.elasticsearch_aggregator.create_dashboard()
            
            # Setup CloudWatch metric filters
            if self.cloudwatch_aggregator.client:
                await self.cloudwatch_aggregator.create_metric_filters()
                
        except Exception as e:
            self.logger.error("Failed to setup monitoring", error=e)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current aggregation metrics."""
        return asdict(self.metrics)


# Global log aggregation manager
log_aggregation_manager = LogAggregationManager()