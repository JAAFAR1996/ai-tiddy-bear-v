#!/usr/bin/env bash
set -e

echo "🚀 AI Teddy Bear - Production Start (Memory Optimized)"
echo "======================================================"

# Environment setup
export PYTHONPATH=/app
export WEB_CONCURRENCY=1
export GUNICORN_WORKERS=1
export PYTHONUNBUFFERED=1
export MALLOC_TRIM_THRESHOLD_=100000

# Memory optimization settings
ulimit -m 450000  # Limit to 450MB (leaving 62MB buffer)

# Server configuration
PORT=${PORT:-8000}
TIMEOUT=${WORKER_TIMEOUT:-120}

echo "📊 Memory-optimized configuration:"
echo "   - Workers: 1 (single worker mode)"
echo "   - Port: $PORT"
echo "   - Timeout: ${TIMEOUT}s"
echo "   - Memory limit: 450MB"
echo ""

# Start server without migrations (handled in preDeploy)
exec gunicorn \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 1 \
    --bind 0.0.0.0:$PORT \
    --timeout $TIMEOUT \
    --keep-alive 2 \
    --max-requests 500 \
    --max-requests-jitter 50 \
    --worker-tmp-dir /dev/shm \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    --preload \
    src.main:app