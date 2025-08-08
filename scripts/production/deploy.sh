#!/bin/bash

# AI Teddy Bear Production Deployment Script
# Usage: ./deploy.sh [environment] [version]

set -e

# Configuration
ENVIRONMENT=${1:-production}
VERSION=${2:-latest}
APP_NAME="ai-teddy-bear"
DOCKER_REGISTRY=${DOCKER_REGISTRY:-"registry.aiteddybear.com"}
BACKUP_DIR="/backups"
LOG_FILE="/var/log/ai-teddy-deploy.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Pre-deployment checks
pre_deployment_checks() {
    log "Running pre-deployment checks..."
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        error "Docker is not running"
    fi
    
    # Check if docker-compose is available
    if ! command -v docker-compose > /dev/null 2>&1; then
        error "docker-compose is not installed"
    fi
    
    # Check environment file
    if [ ! -f ".env.${ENVIRONMENT}" ]; then
        error "Environment file .env.${ENVIRONMENT} not found"
    fi
    
    # Check required environment variables
    source ".env.${ENVIRONMENT}"
    
    required_vars=("DB_PASSWORD" "REDIS_PASSWORD" "SECRET_KEY" "JWT_SECRET_KEY" "ENCRYPTION_KEY")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            error "Required environment variable $var is not set"
        fi
    done
    
    success "Pre-deployment checks passed"
}

# Create backup before deployment
create_backup() {
    log "Creating backup before deployment..."
    
    # Create backup directory if it doesn't exist
    mkdir -p "$BACKUP_DIR"
    
    # Backup database
    BACKUP_FILE="$BACKUP_DIR/ai-teddy-backup-$(date +%Y%m%d-%H%M%S).sql"
    
    if docker-compose exec -T postgres pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_FILE"; then
        success "Database backup created: $BACKUP_FILE"
    else
        warning "Database backup failed, continuing with deployment..."
    fi
    
    # Backup application data
    if [ -d "./data" ]; then
        tar -czf "$BACKUP_DIR/app-data-$(date +%Y%m%d-%H%M%S).tar.gz" ./data
        success "Application data backup created"
    fi
}

# Build and deploy application
deploy_application() {
    log "Starting deployment of $APP_NAME version $VERSION..."
    
    # Copy environment file
    cp ".env.${ENVIRONMENT}" .env
    
    # Build Docker image
    log "Building Docker image..."
    if docker-compose build app; then
        success "Docker image built successfully"
    else
        error "Failed to build Docker image"
    fi
    
    # Pull latest database and redis images
    log "Pulling latest service images..."
    docker-compose pull postgres redis nginx
    
    # Stop existing services gracefully
    log "Stopping existing services..."
    docker-compose down --timeout 30
    
    # Run database migrations
    log "Running database migrations..."
    docker-compose run --rm app python -m alembic upgrade head
    
    # Start services
    log "Starting services..."
    docker-compose up -d
    
    # Wait for services to be healthy
    log "Waiting for services to be healthy..."
    timeout=300
    while [ $timeout -gt 0 ]; do
        if docker-compose ps | grep -q "Up (healthy)"; then
            success "Services are healthy"
            break
        fi
        sleep 5
        timeout=$((timeout - 5))
    done
    
    if [ $timeout -eq 0 ]; then
        error "Services failed to become healthy within 5 minutes"
    fi
}

# Post-deployment verification
post_deployment_verification() {
    log "Running post-deployment verification..."
    
    # Health check
    if curl -f -s "http://localhost:8000/api/v1/health" > /dev/null; then
        success "Health check passed"
    else
        error "Health check failed"
    fi
    
    # Database connectivity
    if docker-compose exec -T app python -c "
import asyncpg
import asyncio
import os

async def test_db():
    try:
        conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
        await conn.fetch('SELECT 1')
        await conn.close()
        print('Database connection successful')
    except Exception as e:
        print(f'Database connection failed: {e}')
        exit(1)

asyncio.run(test_db())
"; then
        success "Database connectivity verified"
    else
        error "Database connectivity check failed"
    fi
    
    # Redis connectivity
    if docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
        success "Redis connectivity verified"
    else
        error "Redis connectivity check failed"
    fi
    
    success "Post-deployment verification completed"
}

# Cleanup old images and containers
cleanup() {
    log "Cleaning up old Docker images..."
    
    # Remove old images (keep last 3 versions)
    docker images "$APP_NAME" --format "table {{.Tag}}\t{{.ID}}" | tail -n +4 | awk '{print $2}' | xargs -r docker rmi
    
    # Remove dangling images
    docker image prune -f
    
    # Remove old containers
    docker container prune -f
    
    success "Cleanup completed"
}

# Main deployment function
main() {
    log "Starting deployment process..."
    log "Environment: $ENVIRONMENT"
    log "Version: $VERSION"
    
    pre_deployment_checks
    create_backup
    deploy_application
    post_deployment_verification
    cleanup
    
    success "Deployment completed successfully!"
    log "Application is now running at: http://localhost:8000"
    log "API Documentation: http://localhost:8000/docs"
    log "Health Check: http://localhost:8000/api/v1/health"
}

# Error handling
trap 'error "Deployment failed at line $LINENO"' ERR

# Run main function
main "$@"
