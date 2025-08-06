"""
Logging Examples - Comprehensive Usage Examples
==============================================
Examples showing how to use the production logging system:
- ELK Stack integration
- CloudWatch Logs integration
- FastAPI middleware integration
- Structured logging with correlation IDs
- Child safety and security logging
- Performance monitoring
- Business logic logging
"""

import asyncio
import os
import time
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from uuid import uuid4

from . import (
    # Core logging
    StructuredLogger, LogLevel, LogCategory, LogContext,
    get_logger, set_log_context, with_log_context,
    
    # Pre-configured loggers
    http_logger, database_logger, cache_logger, provider_logger,
    security_logger, child_safety_logger, performance_logger,
    business_logger, system_logger, audit_logger,
    
    # Middleware and integration
    setup_logging_middleware, logging_integration,
    log_database_operation, log_provider_call, log_cache_operation,
    log_business_operation,
    
    # Aggregation
    log_aggregation_manager, configure_logging, setup_fastapi_logging
)


def example_basic_logging():
    """Example of basic structured logging."""
    print("🔍 Basic Logging Example")
    print("=" * 50)
    
    # Get a logger
    logger = get_logger("example_service")
    
    # Basic logging
    logger.info("Service started", category=LogCategory.SYSTEM)
    logger.debug("Debug information", category=LogCategory.APPLICATION, debug_data={"key": "value"})
    logger.warning("Warning message", category=LogCategory.APPLICATION, warning_type="config")
    logger.error("Error occurred", category=LogCategory.APPLICATION, error_code="E001")
    
    print("✅ Basic logging examples completed")


def example_context_logging():
    """Example of logging with context and correlation IDs."""
    print("\n🔗 Context Logging Example")
    print("=" * 50)
    
    logger = get_logger("context_service")
    
    # Set a log context
    context = LogContext(
        correlation_id=str(uuid4()),
        user_id="user_123",
        child_id="child_456",
        operation="story_generation",
        component="story_service"
    )
    
    set_log_context(context)
    
    # All logs will now include this context
    logger.info("Story generation started", category=LogCategory.BUSINESS)
    logger.info("AI provider selected", category=LogCategory.PROVIDER, provider="openai")
    logger.info("Story generation completed", category=LogCategory.BUSINESS, story_length=150)
    
    print("✅ Context logging examples completed")


@with_log_context(operation="decorated_function", component="example")
def example_decorated_function():
    """Example of using the logging context decorator."""
    logger = get_logger("decorated_service")
    
    logger.info("Function started", category=LogCategory.APPLICATION)
    logger.info("Processing data", category=LogCategory.BUSINESS, data_size=100)
    logger.info("Function completed", category=LogCategory.APPLICATION)


def example_child_safety_logging():
    """Example of child safety specific logging."""
    print("\n🛡️ Child Safety Logging Example")
    print("=" * 50)
    
    child_id = "child_789"
    
    # Log child interaction
    child_safety_logger.child_safety(
        "Child started conversation",
        child_id=child_id,
        safety_flags={"age_appropriate": True, "content_filtered": True},
        metadata={
            "interaction_type": "conversation",
            "session_start": datetime.now().isoformat()
        }
    )
    
    # Log safety violation
    child_safety_logger.warning(
        "Inappropriate content detected",
        category=LogCategory.CHILD_SAFETY,
        child_id=child_id,
        child_safety_flags={
            "violation_type": "inappropriate_language",
            "severity": "medium",
            "action_taken": "content_blocked"
        }
    )
    
    # Log compliance event
    child_safety_logger.compliance(
        "COPPA compliance check performed",
        compliance_type="coppa",
        tags=["age_verification", "parental_consent"],
        metadata={
            "child_id": child_id,
            "parent_consent": True,
            "age_verified": True
        }
    )
    
    print("✅ Child safety logging examples completed")


def example_security_logging():
    """Example of security logging."""
    print("\n🔒 Security Logging Example")
    print("=" * 50)
    
    # Authentication event
    security_logger.info(
        "User authentication attempt",
        category=LogCategory.SECURITY,
        metadata={
            "user_id": "user_123",
            "auth_method": "jwt",
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0...",
            "result": "success"
        }
    )
    
    # Security violation
    security_logger.security(
        "Suspicious activity detected",
        metadata={
            "violation_type": "rate_limit_exceeded",
            "source_ip": "10.0.0.1",
            "attempts": 50,
            "time_window": "5_minutes",
            "action_taken": "ip_blocked"
        }
    )
    
    # Audit event
    audit_logger.audit(
        "Admin action performed",
        metadata={
            "admin_user": "admin_123",
            "action": "user_data_export",
            "target_user": "user_456",
            "timestamp": datetime.now().isoformat(),
            "ip_address": "10.0.0.5"
        }
    )
    
    print("✅ Security logging examples completed")


def example_performance_logging():
    """Example of performance monitoring with logging."""
    print("\n⚡ Performance Logging Example")
    print("=" * 50)
    
    logger = get_logger("performance_service")
    
    # Start timing an operation
    operation_id = logger.start_operation("database_query", table="users", query_type="select")
    
    # Simulate some work
    time.sleep(0.1)
    
    # End timing
    logger.end_operation(operation_id, "database_query", success=True, rows_returned=25)
    
    # Manual performance logging
    performance_logger.info(
        "API endpoint performance",
        category=LogCategory.PERFORMANCE,
        duration_ms=120.5,
        performance_metrics={
            "endpoint": "/api/stories",
            "method": "POST",
            "response_time_ms": 120.5,
            "cpu_usage": 15.2,
            "memory_usage_mb": 45.8,
            "database_queries": 3,
            "cache_hits": 2,
            "cache_misses": 1
        }
    )
    
    print("✅ Performance logging examples completed")


@log_database_operation("select", "stories")
async def example_database_operation():
    """Example of database operation logging."""
    # Simulate database work
    await asyncio.sleep(0.05)
    return {"story_id": "story_123", "title": "Adventure Story"}


@log_provider_call("openai", "ai_provider", "generate_story")
async def example_provider_call():
    """Example of provider call logging."""
    # Simulate provider API call
    await asyncio.sleep(0.2)
    return {"generated_story": "Once upon a time..."}


@log_cache_operation("redis", "get")
async def example_cache_operation():
    """Example of cache operation logging."""
    # Simulate cache lookup
    await asyncio.sleep(0.001)
    return {"cached_data": "some_value"}


@log_business_operation("story_generation", "child_456")
async def example_business_operation():
    """Example of business operation logging."""
    # Simulate business logic
    await asyncio.sleep(0.1)
    return {"story_id": "story_789", "word_count": 150}


async def example_async_logging_operations():
    """Example of async logging operations."""
    print("\n🔄 Async Operations Logging Example")
    print("=" * 50)
    
    # Run async operations with logging
    db_result = await example_database_operation()
    print(f"Database result: {db_result}")
    
    provider_result = await example_provider_call()
    print(f"Provider result: {provider_result}")
    
    cache_result = await example_cache_operation()
    print(f"Cache result: {cache_result}")
    
    business_result = await example_business_operation()
    print(f"Business result: {business_result}")
    
    print("✅ Async operations logging examples completed")


def example_elk_cloudwatch_configuration():
    """Example of ELK Stack and CloudWatch configuration."""
    print("\n☁️ ELK/CloudWatch Configuration Example")
    print("=" * 50)
    
    # Configure logging with ELK and CloudWatch
    configure_logging(
        level="INFO",
        elasticsearch_hosts="localhost:9200,elasticsearch-2:9200",
        cloudwatch_log_group="/aws/ai-teddy-bear/production",
        enable_console=True,
        enable_file=True
    )
    
    # Test logging with different destinations
    logger = get_logger("elk_cloudwatch_test")
    
    logger.info(
        "Testing ELK and CloudWatch integration",
        category=LogCategory.SYSTEM,
        metadata={
            "elasticsearch_enabled": bool(os.getenv("ELASTICSEARCH_HOSTS")),
            "cloudwatch_enabled": bool(os.getenv("CLOUDWATCH_LOG_GROUP")),
            "test_timestamp": datetime.now().isoformat()
        }
    )
    
    print("✅ ELK/CloudWatch configuration example completed")


def example_fastapi_integration():
    """Example of FastAPI integration with logging."""
    print("\n🚀 FastAPI Integration Example")
    print("=" * 50)
    
    # Create FastAPI app
    app = FastAPI(title="AI Teddy Bear API", version="1.0.0")
    
    # Setup comprehensive logging
    setup_fastapi_logging(app, enable_all_middleware=True)
    
    # Add some example routes
    @app.get("/health")
    async def health_check():
        logger = get_logger("health_check")
        logger.info("Health check requested", category=LogCategory.HTTP)
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    
    @app.post("/api/stories")
    async def create_story(request: Request):
        logger = get_logger("story_creation")
        
        # Set context for this request
        context = LogContext(
            correlation_id=str(uuid4()),
            child_id=request.headers.get("x-child-id"),
            parent_id=request.headers.get("x-parent-id"),
            operation="create_story",
            component="story_api"
        )
        set_log_context(context)
        
        # Business logic with logging
        logger.info("Story creation started", category=LogCategory.BUSINESS)
        
        # Simulate some processing
        await asyncio.sleep(0.1)
        
        story_data = {
            "story_id": str(uuid4()),
            "title": "Generated Story",
            "content": "Once upon a time...",
            "created_at": datetime.now().isoformat()
        }
        
        logger.info(
            "Story creation completed",
            category=LogCategory.BUSINESS,
            metadata={
                "story_id": story_data["story_id"],
                "story_length": len(story_data["content"])
            }
        )
        
        return story_data
    
    print("✅ FastAPI integration example completed")
    print(f"App configured with logging middleware and routes")
    print("Available routes: /health, /api/stories, /api/logging/metrics, /api/logging/health")
    
    return app


async def example_log_aggregation():
    """Example of log aggregation with ELK and CloudWatch."""
    print("\n📊 Log Aggregation Example")
    print("=" * 50)
    
    try:
        # Start log aggregation manager
        await log_aggregation_manager.start()
        
        # Generate some test logs
        logger = get_logger("aggregation_test")
        
        for i in range(10):
            logger.info(
                f"Test log message {i+1}",
                category=LogCategory.APPLICATION,
                metadata={
                    "test_run": i+1,
                    "batch_id": "test_batch_001",
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            # Add some variety
            if i % 3 == 0:
                logger.warning(
                    f"Warning test message {i+1}",
                    category=LogCategory.SYSTEM,
                    metadata={"warning_type": "test"}
                )
            
            await asyncio.sleep(0.1)
        
        # Wait for logs to be processed
        await asyncio.sleep(2)
        
        # Get aggregation metrics
        metrics = log_aggregation_manager.get_metrics()
        print(f"Aggregation metrics: {metrics}")
        
        print("✅ Log aggregation example completed")
        
    finally:
        # Stop log aggregation manager
        await log_aggregation_manager.stop()


async def run_all_examples():
    """Run all logging examples."""
    print("🧸 AI Teddy Bear Logging System Examples")
    print("=" * 80)
    
    # Basic examples
    example_basic_logging()
    example_context_logging()
    
    # Decorated function example
    print("\n🎯 Decorated Function Example")
    print("=" * 50)
    example_decorated_function()
    print("✅ Decorated function example completed")
    
    # Specialized logging
    example_child_safety_logging()
    example_security_logging()
    example_performance_logging()
    
    # Async operations
    await example_async_logging_operations()
    
    # Configuration
    example_elk_cloudwatch_configuration()
    
    # FastAPI integration
    app = example_fastapi_integration()
    
    # Log aggregation (commented out to avoid long-running processes)
    # await example_log_aggregation()
    
    print("\n" + "=" * 80)
    print("🎉 All logging examples completed successfully!")
    print("\nTo test the FastAPI integration:")
    print("1. Start the application with: uvicorn main:app --reload")
    print("2. Visit http://localhost:8000/health")
    print("3. Check logs in the ./logs directory")
    print("4. View metrics at http://localhost:8000/api/logging/metrics")
    
    print("\nEnvironment variables for production:")
    print("- LOG_LEVEL=INFO")
    print("- ELASTICSEARCH_HOSTS=localhost:9200")
    print("- CLOUDWATCH_LOG_GROUP=/aws/ai-teddy-bear/production")
    print("- AWS_REGION=us-east-1")


if __name__ == "__main__":
    # Run examples
    asyncio.run(run_all_examples())