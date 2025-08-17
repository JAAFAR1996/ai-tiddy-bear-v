"""
Health check endpoint for logging system
"""
from .structured_logger import StructuredLogger


def logging_health_check():
    """Health check endpoint that returns HTTP 500 if logging is not production ready."""
    health_status = StructuredLogger.get_health_status()
    
    if not health_status["healthy"]:
        return {
            "status": "unhealthy",
            "details": health_status,
            "http_code": 500
        }
    
    return {
        "status": "healthy", 
        "details": health_status,
        "http_code": 200
    }
