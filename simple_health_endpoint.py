"""
Simple health endpoint for debugging
Add this to main.py temporarily to bypass readiness check
"""

@app.get("/health-simple")
async def simple_health_check():
    """Simple health check without readiness validation."""
    import time
    import os
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "environment": os.environ.get("ENVIRONMENT", "unknown"),
        "host": os.environ.get("PUBLIC_HOST", "unknown"),
        "debug": {
            "database_url_set": bool(os.environ.get("DATABASE_URL")),
            "redis_url_set": bool(os.environ.get("REDIS_URL")),
            "openai_key_set": bool(os.environ.get("OPENAI_API_KEY")),
            "elevenlabs_key_set": bool(os.environ.get("ELEVENLABS_API_KEY")),
            "esp32_secret_set": bool(os.environ.get("ESP32_SHARED_SECRET"))
        }
    }