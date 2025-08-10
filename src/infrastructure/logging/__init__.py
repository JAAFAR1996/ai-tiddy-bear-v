"""
🧸 AI TEDDY BEAR V5 - LOGGING INFRASTRUCTURE
==========================================
Production-grade logging with security, COPPA compliance, ELK Stack and CloudWatch integration.
"""

from .production_logger import (
    setup_production_logging,
    get_logger,
    security_logger,
    audit_logger,
    SecurityFilter,
    COPPAComplianceFilter,
    JSONFormatter
)

from .structured_logger import (
    StructuredLogger,
    LogLevel,
    LogCategory,
    LogContext,
    LogEntry,
    LoggingContextManager,
    set_log_context,
    get_log_context,
    # Pre-configured loggers
    http_logger,
    database_logger,
    cache_logger,
    provider_logger,
    child_safety_logger,
    compliance_logger,
    performance_logger,
    business_logger,
    system_logger
)

from .logging_middleware import (
    RequestLoggingMiddleware,
    SecurityLoggingMiddleware,
    ChildSafetyLoggingMiddleware,
    setup_logging_middleware
)

from .logging_integration import (
    LoggingIntegration,
    logging_integration,
    logging_lifespan,
    log_database_operation,
    log_provider_call,
    log_cache_operation,
    log_business_operation,
    add_logging_routes,
    create_logging_app,
    setup_logging_integration,
    logging_app
)

from .log_aggregation import (
    LogAggregationConfig,
    LogDestination,
    LogMetrics,
    ElasticsearchAggregator,
    CloudWatchAggregator,
    LogAggregationManager,
    log_aggregation_manager
)

__all__ = [
    # Legacy compatibility
    'setup_production_logging',
    'get_logger',
    'security_logger',
    'audit_logger',
    'SecurityFilter',
    'COPPAComplianceFilter',
    'JSONFormatter',
    
    # New structured logging
    'StructuredLogger',
    'LogLevel',
    'LogCategory', 
    'LogContext',
    'LogEntry',
    'LoggingContextManager',
    'set_log_context',
    'get_log_context',
    'with_log_context',
    
    # Pre-configured loggers
    'http_logger',
    'database_logger',
    'cache_logger',
    'provider_logger',
    'child_safety_logger',
    'compliance_logger',
    'performance_logger',
    'business_logger',
    'system_logger',
    
    # Middleware
    'RequestLoggingMiddleware',
    'SecurityLoggingMiddleware', 
    'ChildSafetyLoggingMiddleware',
    'setup_logging_middleware',
    
    # Integration
    'LoggingIntegration',
    'logging_integration',
    'logging_lifespan',
    'log_database_operation',
    'log_provider_call',
    'log_cache_operation',
    'log_business_operation',
    'add_logging_routes',
    'create_logging_app',
    'setup_logging_integration',
    'logging_app',
    
    # Aggregation
    'LogAggregationConfig',
    'LogDestination',
    'LogMetrics',
    'ElasticsearchAggregator',
    'CloudWatchAggregator',
    'LogAggregationManager',
    'log_aggregation_manager'
]


def configure_logging(
    level: str = "INFO",
    elasticsearch_hosts: str = None,
    cloudwatch_log_group: str = None,
    enable_console: bool = True,
    enable_file: bool = True
):
    """
    Configure logging for the entire application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        elasticsearch_hosts: Comma-separated Elasticsearch hosts
        cloudwatch_log_group: CloudWatch log group name
        enable_console: Enable console logging
        enable_file: Enable file logging
    """
    import os
    
    # Set environment variables for new system
    os.environ["LOG_LEVEL"] = level
    
    if elasticsearch_hosts:
        os.environ["ELASTICSEARCH_HOSTS"] = elasticsearch_hosts
    
    if cloudwatch_log_group:
        os.environ["CLOUDWATCH_LOG_GROUP"] = cloudwatch_log_group
    
    # Also configure legacy system
    setup_production_logging(
        log_level=level,
        enable_console=enable_console,
        enable_file=enable_file
    )


def setup_fastapi_logging(app, enable_all_middleware: bool = True):
    """
    Setup logging for a FastAPI application.
    
    Args:
        app: FastAPI application instance
        enable_all_middleware: Enable all logging middleware
    """
    if enable_all_middleware:
        setup_logging_middleware(app)
    
    # Add logging routes
    add_logging_routes(app)
    
    # Setup lifespan if not already configured
    if not hasattr(app, 'router') or not app.router.lifespan_context:
        app.router.lifespan_context = logging_lifespan


# Initialize logging on import
configure_logging()
