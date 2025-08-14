#!/usr/bin/env bash
set -e

echo "🚀 AI Teddy Bear - Production Deployment with Automatic Migrations"
echo "=================================================================="

# Colors for better logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Set Python path for proper imports
export PYTHONPATH=/app

# Ensure we're in the right directory
cd /app

log_info "Starting pre-flight checks..."

# =============================================================================
# PRE-FLIGHT CHECKS
# =============================================================================

log_info "1/5 Checking required files..."

# Check for alembic.ini
if [[ ! -f "/app/alembic.ini" ]]; then
    log_error "alembic.ini not found in /app"
    log_error "Available files in /app:"
    ls -la /app/ | head -10
    exit 1
fi
log_success "alembic.ini found"

# Check for migrations directory
if [[ ! -d "/app/migrations" ]]; then
    log_error "migrations/ directory not found in /app"
    log_error "Available directories in /app:"
    ls -la /app/ | grep "^d"
    exit 1
fi
log_success "migrations/ directory found"

# Check for migration files
migration_count=$(find /app/migrations/versions -name "*.py" 2>/dev/null | wc -l || echo "0")
if [[ $migration_count -eq 0 ]]; then
    log_warning "No migration files found in /app/migrations/versions"
    log_warning "This might be the first deployment"
else
    log_success "Found $migration_count migration files"
fi

log_info "2/5 Checking environment variables..."

# Verify we have the required environment variables
if [[ -z "$DATABASE_URL" ]]; then
    log_error "DATABASE_URL environment variable is not set!"
    log_error "This is required for database migrations."
    exit 1
fi
log_success "DATABASE_URL is configured"

# Extract database connection info (safely)
db_host=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\).*/\1/p')
db_name=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')

log_info "Environment details:"
echo "   - Python Path: $PYTHONPATH"
echo "   - Working Dir: $(pwd)"
echo "   - Database Host: ${db_host:-unknown}"
echo "   - Database Name: ${db_name:-unknown}"
echo "   - Environment: ${ENVIRONMENT:-production}"

log_info "3/5 Testing database connectivity..."

# Database ping test
log_info "Attempting to connect to database..."
if timeout 30 python3 -c "
import asyncpg
import asyncio
import os

async def test_connection():
    try:
        conn = await asyncpg.connect(os.environ['DATABASE_URL'], command_timeout=10)
        await conn.execute('SELECT 1')
        await conn.close()
        print('Database connection successful')
        return True
    except Exception as e:
        print(f'Database connection failed: {e}')
        return False

result = asyncio.run(test_connection())
exit(0 if result else 1)
" 2>/dev/null; then
    log_success "Database is accessible"
else
    log_error "Cannot connect to database!"
    log_error "Please check:"
    log_error "  1. DATABASE_URL is correct"
    log_error "  2. Database server is running"
    log_error "  3. Network connectivity"
    log_error "  4. Database credentials"
    exit 1
fi

log_info "4/5 Checking current migration status..."

# Check current migration status first
current_migration=$(alembic -c /app/alembic.ini current 2>/dev/null | grep -E '^[a-f0-9]+' | head -1 || echo "none")
if [[ "$current_migration" == "none" ]]; then
    log_warning "No current migration found - this might be the first deployment"
else
    log_success "Current migration: $current_migration"
fi

# =============================================================================
# DATABASE MIGRATIONS
# =============================================================================

echo ""
log_info "5/5 Running database migrations..."
echo "====================================="

migration_start_time=$(date +%s)

# Run migrations with comprehensive error handling
if alembic -c /app/alembic.ini upgrade head; then
    migration_end_time=$(date +%s)
    migration_duration=$((migration_end_time - migration_start_time))
    log_success "Database migrations completed successfully in ${migration_duration}s"
    
    # Verify final migration status
    final_migration=$(alembic -c /app/alembic.ini current 2>/dev/null | grep -E '^[a-f0-9]+' | head -1 || echo "unknown")
    log_success "Final migration: $final_migration"
else
    log_error "DATABASE MIGRATION FAILED!"
    log_error "This is a CRITICAL error. The application cannot start safely."
    log_error ""
    log_error "Common causes:"
    log_error "  1. Database schema conflicts"
    log_error "  2. Missing database permissions"
    log_error "  3. Network connectivity issues"
    log_error "  4. Corrupted migration files"
    log_error ""
    log_error "STOPPING DEPLOYMENT - Manual intervention required"
    exit 1
fi

# =============================================================================
# APPLICATION SERVER STARTUP
# =============================================================================

echo ""
log_success "🎉 Pre-flight checks and migrations completed successfully!"
echo ""
log_info "Starting AI Teddy Bear Application Server..."
echo "=============================================="

# Server configuration
WORKERS=${WEB_CONCURRENCY:-2}
PORT=${PORT:-8000}
TIMEOUT=${WORKER_TIMEOUT:-120}

log_info "Server configuration:"
echo "   - Environment: ${ENVIRONMENT:-production}"
echo "   - Port: $PORT"
echo "   - Workers: $WORKERS"
echo "   - Timeout: ${TIMEOUT}s"
echo "   - Keep Alive: 2s"
echo "   - Max Requests: 1000 (with jitter)"
echo ""

log_info "🚀 Starting gunicorn with Uvicorn workers..."
echo "Ready for production traffic! 🧸✨"
echo ""

# Use exec to replace the shell process with gunicorn
# This ensures proper signal handling and process management in containers
exec gunicorn \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers $WORKERS \
    --bind 0.0.0.0:$PORT \
    --timeout $TIMEOUT \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --worker-tmp-dir /dev/shm \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    --enable-stdio-inheritance \
    src.main:app