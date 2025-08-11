"""
Advanced Application Performance Monitoring (APM) - AI Teddy Bear
===============================================================
Production-grade APM with distributed tracing, performance profiling,
and child safety-focused monitoring.

Features:
- OpenTelemetry distributed tracing
- Performance profiling and bottleneck detection  
- Child safety request flow tracking
- AI provider latency monitoring
- Database query performance analysis
- Memory leak detection
- Custom business metric tracing

Author: Senior Engineering Team
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import json
import traceback

# OpenTelemetry imports
from opentelemetry import trace, metrics, baggage
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

# Sentry for error tracking
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration

logger = logging.getLogger(__name__)


@dataclass
class APMConfig:
    """Configuration for APM system."""
    service_name: str = "ai-teddy-bear"
    service_version: str = "2.0.0"
    environment: str = "production"
    
    # Jaeger configuration
    jaeger_endpoint: str = "http://jaeger-collector:14268/api/traces"
    
    # Sentry configuration  
    sentry_dsn: Optional[str] = None
    sentry_sample_rate: float = 1.0
    sentry_traces_sample_rate: float = 0.1  # 10% of transactions
    
    # Performance thresholds
    slow_request_threshold_ms: int = 2000    # Child attention span
    database_slow_query_threshold_ms: int = 500
    ai_provider_slow_threshold_ms: int = 1500
    
    # Child safety specific
    enable_child_safety_tracking: bool = True
    track_content_filtering: bool = True
    track_parental_consent: bool = True


class ChildSafetyTracer:
    """Specialized tracer for child safety operations."""
    
    def __init__(self, tracer: trace.Tracer):
        self.tracer = tracer
        
    @asynccontextmanager
    async def trace_content_filtering(
        self, 
        content: str, 
        child_id: str, 
        filter_type: str
    ):
        """Trace content filtering operations with child safety context."""
        with self.tracer.start_as_current_span(
            "content_filtering",
            attributes={
                "child_safety.filter_type": filter_type,
                "child_safety.child_id": child_id,
                "child_safety.content_length": len(content),
                "child_safety.timestamp": datetime.utcnow().isoformat(),
            }
        ) as span:
            # Add child safety baggage for downstream services
            baggage_ctx = baggage.set_baggage("child_safety.active", "true")
            baggage_ctx = baggage.set_baggage("child_safety.child_id", child_id, baggage_ctx)
            
            try:
                yield span
                span.set_attribute("child_safety.filter_result", "passed")
                span.set_status(trace.Status(trace.StatusCode.OK))
            except Exception as e:
                span.set_attribute("child_safety.filter_result", "blocked")
                span.set_attribute("child_safety.violation_reason", str(e))
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
                
    @asynccontextmanager 
    async def trace_parental_consent(
        self,
        child_id: str,
        consent_action: str,
        parent_id: Optional[str] = None
    ):
        """Trace parental consent operations."""
        with self.tracer.start_as_current_span(
            "parental_consent_check",
            attributes={
                "coppa.child_id": child_id,
                "coppa.action": consent_action,
                "coppa.parent_id": parent_id or "unknown",
                "coppa.timestamp": datetime.utcnow().isoformat(),
            }
        ) as span:
            try:
                yield span
                span.set_attribute("coppa.consent_valid", "true")
                span.set_status(trace.Status(trace.StatusCode.OK))
            except Exception as e:
                span.set_attribute("coppa.consent_valid", "false") 
                span.set_attribute("coppa.violation", str(e))
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise


class AIProviderTracer:
    """Specialized tracer for AI provider interactions."""
    
    def __init__(self, tracer: trace.Tracer, config: APMConfig):
        self.tracer = tracer
        self.config = config
        
    @asynccontextmanager
    async def trace_ai_request(
        self,
        provider: str,
        operation: str,
        input_tokens: Optional[int] = None,
        max_tokens: Optional[int] = None
    ):
        """Trace AI provider requests with detailed metrics."""
        start_time = time.time()
        
        with self.tracer.start_as_current_span(
            f"ai_provider_{operation}",
            attributes={
                "ai.provider": provider,
                "ai.operation": operation,
                "ai.input_tokens": input_tokens or 0,
                "ai.max_tokens": max_tokens or 0,
                "ai.start_time": start_time,
            }
        ) as span:
            try:
                yield span
                
                # Calculate and record performance metrics
                duration_ms = (time.time() - start_time) * 1000
                span.set_attribute("ai.duration_ms", duration_ms)
                
                # Check if request was slow
                if duration_ms > self.config.ai_provider_slow_threshold_ms:
                    span.set_attribute("ai.slow_request", True)
                    logger.warning(
                        f"Slow AI request: {provider} {operation} took {duration_ms:.2f}ms"
                    )
                
                span.set_status(trace.Status(trace.StatusCode.OK))
                
            except Exception as e:
                span.set_attribute("ai.error", str(e))
                span.set_attribute("ai.error_type", type(e).__name__)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise


class DatabaseTracer:
    """Specialized tracer for database operations."""
    
    def __init__(self, tracer: trace.Tracer, config: APMConfig):
        self.tracer = tracer
        self.config = config
        
    @asynccontextmanager
    async def trace_database_operation(
        self,
        operation: str,
        table: str,
        query: Optional[str] = None
    ):
        """Trace database operations with performance monitoring."""
        start_time = time.time()
        
        with self.tracer.start_as_current_span(
            f"db_{operation}",
            attributes={
                "db.operation": operation,
                "db.table": table,
                "db.query": query[:100] + "..." if query and len(query) > 100 else query,
                "db.start_time": start_time,
            }
        ) as span:
            try:
                yield span
                
                # Performance analysis
                duration_ms = (time.time() - start_time) * 1000
                span.set_attribute("db.duration_ms", duration_ms)
                
                if duration_ms > self.config.database_slow_query_threshold_ms:
                    span.set_attribute("db.slow_query", True)
                    logger.warning(
                        f"Slow database query: {operation} on {table} took {duration_ms:.2f}ms"
                    )
                
                span.set_status(trace.Status(trace.StatusCode.OK))
                
            except Exception as e:
                span.set_attribute("db.error", str(e))
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise


class AdvancedAPMManager:
    """
    Production-grade APM manager for AI Teddy Bear platform.
    
    Provides comprehensive monitoring with focus on:
    - Child safety operation tracing
    - AI provider performance monitoring  
    - Database query optimization
    - Business transaction tracking
    - Error correlation and root cause analysis
    """
    
    def __init__(self, config: APMConfig):
        self.config = config
        self.tracer_provider = None
        self.meter_provider = None
        self.tracer = None
        self.meter = None
        
        # Specialized tracers
        self.child_safety_tracer = None
        self.ai_provider_tracer = None
        self.database_tracer = None
        
        # Performance counters
        self.performance_counters = {
            'slow_requests': 0,
            'database_slow_queries': 0,
            'ai_provider_timeouts': 0,
            'child_safety_violations': 0,
            'memory_pressure_events': 0
        }
        
    async def initialize(self):
        """Initialize APM system with all components."""
        try:
            # Initialize OpenTelemetry tracing
            await self._setup_tracing()
            
            # Initialize metrics
            await self._setup_metrics()
            
            # Initialize Sentry
            await self._setup_sentry()
            
            # Initialize specialized tracers
            await self._setup_specialized_tracers()
            
            # Setup instrumentation
            await self._setup_instrumentation()
            
            logger.info(f"APM system initialized for {self.config.service_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize APM system: {e}", exc_info=True)
            raise
            
    async def _setup_tracing(self):
        """Setup distributed tracing with Jaeger."""
        # Create resource with service information
        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: self.config.service_name,
            ResourceAttributes.SERVICE_VERSION: self.config.service_version,
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: self.config.environment,
            "child_safety.enabled": str(self.config.enable_child_safety_tracking),
        })
        
        # Create tracer provider
        self.tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(self.tracer_provider)
        
        # Setup Jaeger exporter
        jaeger_exporter = JaegerExporter(
            endpoint=self.config.jaeger_endpoint,
        )
        
        # Add span processor
        span_processor = BatchSpanProcessor(jaeger_exporter)
        self.tracer_provider.add_span_processor(span_processor)
        
        # Set up B3 propagation for microservices
        set_global_textmap(B3MultiFormat())
        
        # Get tracer instance
        self.tracer = trace.get_tracer(
            __name__,
            version=self.config.service_version
        )
        
    async def _setup_metrics(self):
        """Setup metrics collection."""
        # Prometheus metrics reader
        prometheus_reader = PrometheusMetricReader()
        
        # Create meter provider
        self.meter_provider = MeterProvider(
            resource=Resource.create({
                ResourceAttributes.SERVICE_NAME: self.config.service_name,
            }),
            metric_readers=[prometheus_reader]
        )
        
        metrics.set_meter_provider(self.meter_provider)
        self.meter = metrics.get_meter(__name__)
        
        # Create custom metrics
        self._setup_custom_metrics()
        
    def _setup_custom_metrics(self):
        """Setup custom business metrics."""
        # Child safety metrics
        self.child_safety_violations_counter = self.meter.create_counter(
            "child_safety_violations_total",
            description="Total child safety violations detected",
            unit="1"
        )
        
        self.content_filter_duration = self.meter.create_histogram(
            "content_filter_duration_seconds",
            description="Time spent on content filtering",
            unit="s"
        )
        
        # AI provider metrics
        self.ai_request_duration = self.meter.create_histogram(
            "ai_request_duration_seconds",
            description="AI provider request duration",
            unit="s"
        )
        
        self.ai_request_tokens = self.meter.create_histogram(
            "ai_request_tokens_total",
            description="Tokens processed in AI requests",
            unit="1"
        )
        
        # Database metrics
        self.database_query_duration = self.meter.create_histogram(
            "database_query_duration_seconds", 
            description="Database query execution time",
            unit="s"
        )
        
        # Business metrics
        self.child_interactions_counter = self.meter.create_counter(
            "child_interactions_total",
            description="Total child interactions",
            unit="1"
        )
        
        self.parent_satisfaction_gauge = self.meter.create_up_down_counter(
            "parent_satisfaction_score",
            description="Parent satisfaction score",
            unit="1"
        )
        
    async def _setup_sentry(self):
        """Setup Sentry error tracking."""
        if not self.config.sentry_dsn:
            logger.info("Sentry DSN not configured, skipping Sentry setup")
            return
            
        sentry_sdk.init(
            dsn=self.config.sentry_dsn,
            environment=self.config.environment,
            release=f"{self.config.service_name}@{self.config.service_version}",
            
            # Performance monitoring
            traces_sample_rate=self.config.sentry_traces_sample_rate,
            profiles_sample_rate=0.1,  # 10% of transactions
            
            # Integrations
            integrations=[
                FastApiIntegration(auto_enabling_integrations=True),
                AsyncioIntegration(),
            ],
            
            # Child safety context
            before_send=self._sentry_before_send,
            
            # Advanced configuration
            attach_stacktrace=True,
            send_default_pii=False,  # COPPA compliance - no PII
            max_breadcrumbs=50,
        )
        
        logger.info("Sentry error tracking initialized")
        
    def _sentry_before_send(self, event: Dict, hint: Dict) -> Optional[Dict]:
        """Filter and enhance Sentry events with child safety context."""
        # Add child safety context if available
        if baggage.get_baggage("child_safety.active"):
            event.setdefault("tags", {})["child_safety"] = "active"
            
            # Remove any potential PII for COPPA compliance
            child_id = baggage.get_baggage("child_safety.child_id")
            if child_id:
                # Hash the child ID for correlation without exposing PII
                import hashlib
                hashed_id = hashlib.sha256(child_id.encode()).hexdigest()[:8]
                event["tags"]["child_session"] = hashed_id
                
        # Enhance error context
        if "exception" in event:
            # Add performance context for errors
            event.setdefault("extra", {}).update({
                "performance_counters": self.performance_counters.copy(),
                "service_health": self._get_service_health_snapshot()
            })
            
        return event
        
    async def _setup_specialized_tracers(self):
        """Setup specialized tracers for different domains."""
        self.child_safety_tracer = ChildSafetyTracer(self.tracer)
        self.ai_provider_tracer = AIProviderTracer(self.tracer, self.config)
        self.database_tracer = DatabaseTracer(self.tracer, self.config)
        
    async def _setup_instrumentation(self):
        """Setup automatic instrumentation for common libraries."""
        # FastAPI instrumentation
        FastAPIInstrumentor.instrument()
        
        # HTTP client instrumentation
        HTTPXClientInstrumentor.instrument()
        
        # Database instrumentation
        Psycopg2Instrumentor.instrument()
        
        # Redis instrumentation  
        RedisInstrumentor.instrument()
        
    @asynccontextmanager
    async def trace_business_transaction(
        self,
        transaction_name: str,
        user_id: Optional[str] = None,
        child_id: Optional[str] = None,
        **attributes
    ):
        """Trace high-level business transactions."""
        with self.tracer.start_as_current_span(
            transaction_name,
            attributes={
                "business.transaction": transaction_name,
                "business.user_id": user_id or "anonymous",
                "business.child_id": child_id or "none",
                "business.timestamp": datetime.utcnow().isoformat(),
                **attributes
            }
        ) as span:
            # Set baggage for downstream services
            if child_id:
                baggage_ctx = baggage.set_baggage("business.child_id", child_id)
                
            start_time = time.time()
            
            try:
                yield span
                
                # Record performance metrics
                duration_ms = (time.time() - start_time) * 1000
                span.set_attribute("business.duration_ms", duration_ms)
                
                # Track slow transactions
                if duration_ms > self.config.slow_request_threshold_ms:
                    span.set_attribute("business.slow_transaction", True)
                    self.performance_counters['slow_requests'] += 1
                    
                    # Alert for child attention span violations
                    if child_id:
                        logger.warning(
                            f"Slow child transaction: {transaction_name} "
                            f"took {duration_ms:.2f}ms (threshold: {self.config.slow_request_threshold_ms}ms)"
                        )
                        
                # Record business metrics
                self.child_interactions_counter.add(1, {
                    "transaction": transaction_name,
                    "child_id": child_id or "none"
                })
                
                span.set_status(trace.Status(trace.StatusCode.OK))
                
            except Exception as e:
                span.set_attribute("business.error", str(e))
                span.set_attribute("business.error_type", type(e).__name__)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.record_exception(e)
                
                # Enhance error with context
                sentry_sdk.set_context("business_transaction", {
                    "name": transaction_name,
                    "user_id": user_id,
                    "child_id": child_id,
                    "duration_ms": (time.time() - start_time) * 1000
                })
                
                raise
                
    async def track_performance_anomaly(
        self,
        anomaly_type: str,
        severity: str,
        details: Dict[str, Any]
    ):
        """Track performance anomalies for investigation."""
        with self.tracer.start_as_current_span(
            "performance_anomaly",
            attributes={
                "anomaly.type": anomaly_type,
                "anomaly.severity": severity,
                "anomaly.details": json.dumps(details),
                "anomaly.timestamp": datetime.utcnow().isoformat(),
            }
        ) as span:
            
            # Update performance counters
            counter_key = f"{anomaly_type}_events"
            if counter_key in self.performance_counters:
                self.performance_counters[counter_key] += 1
                
            # Send to Sentry for alerting
            sentry_sdk.capture_message(
                f"Performance anomaly detected: {anomaly_type}",
                level=severity.lower(),
                extra=details
            )
            
            logger.warning(
                f"Performance anomaly: {anomaly_type} ({severity})",
                extra=details
            )
            
    def _get_service_health_snapshot(self) -> Dict[str, Any]:
        """Get current service health snapshot."""
        return {
            "performance_counters": self.performance_counters.copy(),
            "timestamp": datetime.utcnow().isoformat(),
            "service_name": self.config.service_name,
            "environment": self.config.environment
        }
        
    async def flush_telemetry(self):
        """Flush all pending telemetry data."""
        if self.tracer_provider:
            # Force flush traces
            for processor in self.tracer_provider._active_span_processor._span_processors:
                if hasattr(processor, 'force_flush'):
                    processor.force_flush(30000)  # 30 second timeout
                    
        # Flush Sentry
        sentry_sdk.flush(timeout=30)
        
        logger.info("Telemetry data flushed")
        
    async def shutdown(self):
        """Gracefully shutdown APM system."""
        try:
            await self.flush_telemetry()
            
            if self.tracer_provider:
                self.tracer_provider.shutdown()
                
            if self.meter_provider:
                self.meter_provider.shutdown()
                
            logger.info("APM system shut down successfully")
            
        except Exception as e:
            logger.error(f"Error during APM shutdown: {e}", exc_info=True)


# Middleware for automatic request tracing
class APMMiddleware:
    """FastAPI middleware for automatic APM integration."""
    
    def __init__(self, apm_manager: AdvancedAPMManager):
        self.apm_manager = apm_manager
        
    async def __call__(self, request, call_next):
        """Process request with automatic tracing."""
        start_time = time.time()
        
        # Extract child context from request
        child_id = request.headers.get("X-Child-ID")
        user_id = request.headers.get("X-User-ID")
        
        # Determine transaction name
        transaction_name = f"{request.method} {request.url.path}"
        
        # Trace the request
        async with self.apm_manager.trace_business_transaction(
            transaction_name,
            user_id=user_id,
            child_id=child_id,
            http_method=request.method,
            http_path=request.url.path,
            http_user_agent=request.headers.get("User-Agent", "unknown")
        ) as span:
            
            # Process request
            response = await call_next(request)
            
            # Add response attributes
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("http.response_size", 
                             response.headers.get("Content-Length", "0"))
            
            # Track response time
            response_time_ms = (time.time() - start_time) * 1000
            span.set_attribute("http.response_time_ms", response_time_ms)
            
            return response


# Factory function for production use
async def create_apm_manager(
    service_name: str = "ai-teddy-bear",
    environment: str = "production",
    jaeger_endpoint: str = "http://localhost:14268/api/traces",
    sentry_dsn: Optional[str] = None,
    **kwargs
) -> AdvancedAPMManager:
    """Create and initialize APM manager for production use."""
    
    config = APMConfig(
        service_name=service_name,
        environment=environment,
        jaeger_endpoint=jaeger_endpoint,
        sentry_dsn=sentry_dsn,
        **kwargs
    )
    
    apm_manager = AdvancedAPMManager(config)
    await apm_manager.initialize()
    
    return apm_manager


# Example usage for production deployment
if __name__ == "__main__":
    async def main():
        # Create APM manager
        apm_manager = await create_apm_manager(
            service_name="ai-teddy-bear",
            environment="production",
            sentry_dsn="https://your-sentry-dsn@sentry.io/project-id"
        )
        
        # Example business transaction tracing
        async with apm_manager.trace_business_transaction(
            "story_generation",
            child_id="child_123",
            story_type="bedtime"
        ) as span:
            
            # Simulate child safety check
            async with apm_manager.child_safety_tracer.trace_content_filtering(
                "Tell me a bedtime story about dragons",
                "child_123",
                "content_appropriateness"
            ) as safety_span:
                print("Content filtering completed")
                
            # Simulate AI provider call
            async with apm_manager.ai_provider_tracer.trace_ai_request(
                provider="openai",
                operation="story_generation",
                input_tokens=50,
                max_tokens=500
            ) as ai_span:
                print("Story generated by AI")
                
            print("Business transaction completed")
            
        # Flush telemetry
        await apm_manager.flush_telemetry()
        
        # Shutdown
        await apm_manager.shutdown()
    
    asyncio.run(main())