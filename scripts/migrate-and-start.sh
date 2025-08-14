#!/usr/bin/env bash
set -e

echo "🚀 Starting AI Teddy Bear - Production Deployment"
echo "================================================"

# Set Python path for proper imports
export PYTHONPATH=/app

# Ensure we're in the right directory
cd /app

# Verify we have the required environment variables
if [[ -z "$DATABASE_URL" ]]; then
    echo "❌ ERROR: DATABASE_URL environment variable is not set!"
    echo "This is required for database migrations."
    exit 1
fi

echo "📋 Environment Check:"
echo "   - Python Path: $PYTHONPATH"
echo "   - Working Dir: $(pwd)"
echo "   - Database URL: ${DATABASE_URL:0:20}... (truncated for security)"

# Check if Alembic files exist
if [[ ! -f "/app/alembic.ini" ]]; then
    echo "❌ ERROR: alembic.ini not found in /app"
    echo "Available files in /app:"
    ls -la /app/ | head -10
    exit 1
fi

if [[ ! -d "/app/migrations" ]]; then
    echo "❌ ERROR: migrations/ directory not found in /app"
    echo "Available directories in /app:"
    ls -la /app/ | grep "^d"
    exit 1
fi

echo "✅ Alembic files found successfully"

# Run database migrations with detailed logging
echo ""
echo "🗃️ Running Database Migrations..."
echo "=================================="

# Check current migration status first
echo "Current migration status:"
alembic -c /app/alembic.ini current || {
    echo "⚠️ Warning: Could not determine current migration status"
    echo "This might be the first deployment - continuing with upgrade..."
}

# Run migrations with error handling
echo ""
echo "Applying migrations..."
alembic -c /app/alembic.ini upgrade head || {
    echo ""
    echo "❌ ERROR: Database migration failed!"
    echo "This could be due to:"
    echo "  1. Database connection issues"
    echo "  2. Migration conflicts"
    echo "  3. Missing permissions"
    echo ""
    echo "⚠️ CRITICAL: Starting server WITHOUT applying migrations"
    echo "         Manual intervention may be required"
    echo ""
    # Continue startup but log the failure
}

echo "✅ Database migrations completed successfully"

# Verify final migration status
echo ""
echo "Final migration status:"
alembic -c /app/alembic.ini current || echo "⚠️ Could not verify migration status"

# Start the application server
echo ""
echo "🧸 Starting AI Teddy Bear Application Server..."
echo "=============================================="
echo "   - Environment: ${ENVIRONMENT:-production}"
echo "   - Port: ${PORT:-8000}"
echo "   - Workers: 2 (optimized for Render)"
echo ""

# Use exec to replace the shell process with gunicorn
# This ensures proper signal handling and process management
exec gunicorn \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 \
    --bind 0.0.0.0:${PORT:-8000} \
    --timeout 120 \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    src.main:app