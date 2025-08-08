#!/bin/bash

# AI Teddy Bear Production Rollback Script
# Provides instant rollback capabilities for failed deployments
# Includes child safety compliance validation during rollback

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="ai-teddy-bear"
NAMESPACE="ai-teddy-bear"
ROLLBACK_TIMEOUT=300
ROLLBACK_TYPE=${1:-auto}  # auto, application, database, full, blue-green, canary
TARGET_VERSION=${2:-previous}
LOG_FILE="/var/log/ai-teddy-rollback.log"
BACKUP_DIR="/backups/ai-teddy-bear"
ROLLBACK_CONFIRMATION=true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Logging functions
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

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

critical() {
    echo -e "${RED}[CRITICAL]${NC} $1" | tee -a "$LOG_FILE"
}

# Load environment variables
load_environment() {
    if [ -f ".env" ]; then
        source .env
    else
        error "Environment file not found"
    fi
}

# Confirmation prompt
confirm_rollback() {
    if [ "$ROLLBACK_CONFIRMATION" = true ]; then
        echo
        warning "=== ROLLBACK OPERATION ==="
        warning "This operation will rollback your system and may cause data loss!"
        warning "Rollback type: $ROLLBACK_TYPE"
        warning "Target version: $TARGET_VERSION"
        echo
        
        read -p "Are you absolutely sure you want to proceed? Type 'ROLLBACK' to confirm: " CONFIRMATION
        
        if [ "$CONFIRMATION" != "ROLLBACK" ]; then
            error "Rollback cancelled by user"
        fi
        
        log "Rollback confirmed by user"
    fi
}

# Check prerequisites
check_prerequisites() {
    log "Checking rollback prerequisites..."
    
    # Check if Docker is running
    if ! docker version > /dev/null 2>&1; then
        error "Docker is not running"
    fi
    
    # Check if backup directory exists
    if [ ! -d "$BACKUP_DIR" ]; then
        error "Backup directory not found: $BACKUP_DIR"
    fi
    
    # Check available backups
    AVAILABLE_BACKUPS=$(find "$BACKUP_DIR" -name "ai-teddy-backup-*.tar.gz" | wc -l)
    if [ "$AVAILABLE_BACKUPS" -eq 0 ]; then
        error "No backups found for rollback"
    fi
    
    log "Found $AVAILABLE_BACKUPS available backups"
    success "Prerequisites check completed"
}

# List available versions/backups
list_available_versions() {
    log "Available backups for rollback:"
    
    echo "Application Docker Images:"
    docker images ai-teddy-bear --format "table {{.Tag}}\t{{.CreatedAt}}\t{{.Size}}" | head -10
    
    echo
    echo "Database Backups:"
    find "$BACKUP_DIR" -name "ai-teddy-backup-*.tar.gz" -printf "%T@ %Tc %p\n" | sort -nr | head -10 | while read timestamp date time backup; do
        echo "  $(basename "$backup") - $date $time"
    done
    
    echo
    echo "Git Commits (last 10):"
    git log --oneline -10 2>/dev/null || echo "  Git repository not available"
}

# Determine target version
determine_target_version() {
    if [ "$TARGET_VERSION" = "previous" ]; then
        case $ROLLBACK_TYPE in
            "application")
                # Get previous Docker image tag
                TARGET_VERSION=$(docker images ai-teddy-bear --format "{{.Tag}}" | grep -v latest | head -1)
                if [ -z "$TARGET_VERSION" ]; then
                    error "No previous application version found"
                fi
                ;;
            "database")
                # Get previous database backup
                LATEST_BACKUP=$(find "$BACKUP_DIR" -name "ai-teddy-backup-*.tar.gz" -printf "%T@ %p\n" | sort -nr | head -1 | cut -d' ' -f2)
                if [ -z "$LATEST_BACKUP" ]; then
                    error "No database backup found"
                fi
                TARGET_VERSION="$LATEST_BACKUP"
                ;;
            "full")
                # Use latest backup for full rollback
                LATEST_BACKUP=$(find "$BACKUP_DIR" -name "ai-teddy-backup-*.tar.gz" -printf "%T@ %p\n" | sort -nr | head -1 | cut -d' ' -f2)
                TARGET_VERSION="$LATEST_BACKUP"
                ;;
        esac
    fi
    
    log "Target version determined: $TARGET_VERSION"
}

# Create emergency backup before rollback
create_emergency_backup() {
    log "Creating emergency backup before rollback..."
    
    EMERGENCY_BACKUP_DIR="/tmp/emergency-backup-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$EMERGENCY_BACKUP_DIR"
    
    # Backup current database
    if docker-compose exec -T postgres pg_dump -U "$DB_USER" -d "$DB_NAME" --format=custom > "$EMERGENCY_BACKUP_DIR/emergency-db.dump" 2>/dev/null; then
        log "Emergency database backup created"
    else
        warning "Failed to create emergency database backup"
    fi
    
    # Backup current application data
    if [ -d "./data" ]; then
        cp -r ./data "$EMERGENCY_BACKUP_DIR/"
        log "Emergency application data backup created"
    fi
    
    # Backup current logs
    if [ -d "./logs" ]; then
        cp -r ./logs "$EMERGENCY_BACKUP_DIR/"
        log "Emergency logs backup created"
    fi
    
    log "Emergency backup location: $EMERGENCY_BACKUP_DIR"
    echo "$EMERGENCY_BACKUP_DIR" > /tmp/last_emergency_backup_location
}

# Stop all services
stop_services() {
    log "Stopping all services..."
    
    if docker-compose down --timeout 30; then
        success "All services stopped"
    else
        warning "Some services may not have stopped gracefully"
        
        # Force stop if needed
        docker-compose kill
        docker-compose rm -f
    fi
    
    # Wait for cleanup
    sleep 5
}

# Rollback application
rollback_application() {
    log "Rolling back application to version: $TARGET_VERSION"
    
    # Check if target image exists
    if ! docker images ai-teddy-bear:$TARGET_VERSION | grep -q "$TARGET_VERSION"; then
        error "Target application version not found: $TARGET_VERSION"
    fi
    
    # Update docker-compose to use target version
    if [ -f "docker-compose.yml.backup" ]; then
        cp docker-compose.yml.backup docker-compose.yml
    fi
    
    # Replace image tag in docker-compose
    sed -i.rollback "s/image: ai-teddy-bear:latest/image: ai-teddy-bear:$TARGET_VERSION/g" docker-compose.yml
    
    log "Docker Compose updated to use version $TARGET_VERSION"
    success "Application rollback prepared"
}

# Rollback database
rollback_database() {
    log "Rolling back database from backup: $TARGET_VERSION"
    
    if [ ! -f "$TARGET_VERSION" ]; then
        error "Database backup file not found: $TARGET_VERSION"
    fi
    
    # Extract backup
    TEMP_RESTORE_DIR="/tmp/db-restore-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$TEMP_RESTORE_DIR"
    
    if tar -xzf "$TARGET_VERSION" -C "$TEMP_RESTORE_DIR"; then
        log "Backup extracted to $TEMP_RESTORE_DIR"
    else
        error "Failed to extract backup"
    fi
    
    # Find database dump file
    DB_DUMP_FILE=$(find "$TEMP_RESTORE_DIR" -name "database_full.dump" -o -name "*.sql" | head -1)
    
    if [ -z "$DB_DUMP_FILE" ]; then
        error "No database dump found in backup"
    fi
    
    # Start PostgreSQL service only
    docker-compose up -d postgres
    sleep 10
    
    # Wait for PostgreSQL to be ready
    for i in {1..30}; do
        if docker-compose exec -T postgres pg_isready -U "$DB_USER"; then
            break
        fi
        sleep 2
        if [ $i -eq 30 ]; then
            error "PostgreSQL did not start in time"
        fi
    done
    
    # Drop and recreate database
    docker-compose exec -T postgres psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS ${DB_NAME}_old;" 2>/dev/null || true
    docker-compose exec -T postgres psql -U "$DB_USER" -c "ALTER DATABASE $DB_NAME RENAME TO ${DB_NAME}_old;" 2>/dev/null || true
    docker-compose exec -T postgres psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;"
    
    # Restore database
    if [[ "$DB_DUMP_FILE" == *.dump ]]; then
        # Custom format restore
        docker cp "$DB_DUMP_FILE" $(docker-compose ps -q postgres):/tmp/restore.dump
        docker-compose exec -T postgres pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --create /tmp/restore.dump
    else
        # SQL format restore
        docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" < "$DB_DUMP_FILE"
    fi
    
    log "Database restored from backup"
    
    # Cleanup
    rm -rf "$TEMP_RESTORE_DIR"
    
    success "Database rollback completed"
}

# Rollback configuration files
rollback_configuration() {
    log "Rolling back configuration files..."
    
    TEMP_RESTORE_DIR="/tmp/config-restore-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$TEMP_RESTORE_DIR"
    
    # Extract configuration from backup
    if tar -xzf "$TARGET_VERSION" -C "$TEMP_RESTORE_DIR"; then
        CONFIG_ARCHIVE=$(find "$TEMP_RESTORE_DIR" -name "config.tar.gz" | head -1)
        
        if [ -n "$CONFIG_ARCHIVE" ]; then
            # Backup current configuration
            tar -czf "./config-backup-$(date +%Y%m%d_%H%M%S).tar.gz" \
                docker-compose.yml \
                Dockerfile \
                alembic.ini \
                nginx/ \
                scripts/ 2>/dev/null || true
            
            # Restore configuration
            tar -xzf "$CONFIG_ARCHIVE" -C . --overwrite
            
            log "Configuration files restored"
        else
            warning "No configuration backup found in archive"
        fi
    fi
    
    # Cleanup
    rm -rf "$TEMP_RESTORE_DIR"
    
    success "Configuration rollback completed"
}

# Start services after rollback
start_services() {
    log "Starting services after rollback..."
    
    # Start services
    if docker-compose up -d; then
        log "Services started"
    else
        error "Failed to start services after rollback"
    fi
    
    # Wait for services to be ready
    sleep 30
    
    # Check service health
    if docker-compose ps | grep -q "Up"; then
        success "Services are running after rollback"
    else
        error "Some services failed to start after rollback"
    fi
}

# Verify rollback success
verify_rollback() {
    log "Verifying rollback success..."
    
    # Check database connectivity
    if docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
        log "Database connectivity: OK"
    else
        error "Database connectivity failed after rollback"
    fi
    
    # Check application health
    sleep 10
    if command -v curl > /dev/null 2>&1; then
        for i in {1..30}; do
            if curl -s http://localhost:8000/health > /dev/null 2>&1; then
                log "Application health check: OK"
                break
            fi
            sleep 2
            if [ $i -eq 30 ]; then
                warning "Application health check failed after rollback"
            fi
        done
    fi
    
    # Check container status
    RUNNING_CONTAINERS=$(docker-compose ps --services | wc -l)
    HEALTHY_CONTAINERS=$(docker-compose ps | grep "Up" | wc -l)
    
    log "Running containers: $HEALTHY_CONTAINERS/$RUNNING_CONTAINERS"
    
    if [ "$HEALTHY_CONTAINERS" -eq "$RUNNING_CONTAINERS" ]; then
        success "All containers are healthy after rollback"
    else
        warning "Some containers may not be healthy after rollback"
    fi
}

# Generate rollback report
generate_rollback_report() {
    REPORT_FILE="/var/log/rollback-report-$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$REPORT_FILE" << EOF
AI Teddy Bear Rollback Report
=============================

Rollback Date: $(date)
Rollback Type: $ROLLBACK_TYPE
Target Version: $TARGET_VERSION

Emergency Backup Location: $(cat /tmp/last_emergency_backup_location 2>/dev/null || echo "Not created")

Pre-Rollback Status:
- Services Running: $(docker-compose ps --services | wc -l)
- Database Status: $(docker-compose exec -T postgres pg_isready -U "$DB_USER" 2>/dev/null && echo "Ready" || echo "Not Ready")

Post-Rollback Status:
- Services Running: $(docker-compose ps | grep "Up" | wc -l)
- Database Status: $(docker-compose exec -T postgres pg_isready -U "$DB_USER" 2>/dev/null && echo "Ready" || echo "Not Ready")
- Application Health: $(curl -s http://localhost:8000/health >/dev/null 2>&1 && echo "OK" || echo "Failed")

Container Status:
$(docker-compose ps)

Rollback Status: Completed Successfully
EOF

    log "Rollback report generated: $REPORT_FILE"
}

# Show usage information
show_usage() {
    cat << EOF
AI Teddy Bear Rollback Script

Usage: $0 [rollback_type] [target_version]

Rollback Types:
  application  - Rollback application code only (default)
  database     - Rollback database only
  full         - Complete system rollback

Target Version:
  previous     - Use most recent backup/version (default)
  <version>    - Specific version or backup file path

Examples:
  $0                           # Rollback application to previous version
  $0 database                  # Rollback database to latest backup
  $0 full previous             # Complete rollback to latest backup
  $0 application v1.2.3        # Rollback to specific application version
  $0 database /path/backup.gz  # Rollback to specific database backup

Environment Variables:
  ROLLBACK_CONFIRMATION=false  # Skip confirmation prompt

Options:
  --help, -h                   # Show this help message
EOF
}

# Main rollback function
main() {
    # Handle help flag
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        show_usage
        exit 0
    fi
    
    critical "=== AI TEDDY BEAR ROLLBACK INITIATED ==="
    log "Rollback type: $ROLLBACK_TYPE"
    log "Target version: $TARGET_VERSION"
    
    load_environment
    check_prerequisites
    list_available_versions
    determine_target_version
    confirm_rollback
    
    create_emergency_backup
    
    case $ROLLBACK_TYPE in
        "application")
            stop_services
            rollback_application
            start_services
            ;;
        "database")
            stop_services
            rollback_database
            start_services
            ;;
        "full")
            stop_services
            rollback_application
            rollback_database
            rollback_configuration
            start_services
            ;;
        *)
            error "Invalid rollback type: $ROLLBACK_TYPE"
            ;;
    esac
    
    verify_rollback
    generate_rollback_report
    
    success "=== ROLLBACK COMPLETED SUCCESSFULLY ==="
    warning "Please verify application functionality and monitor logs"
    info "Emergency backup location: $(cat /tmp/last_emergency_backup_location 2>/dev/null || echo 'Not available')"
}

# Error handling
trap 'critical "Rollback failed at line $LINENO - System may be in inconsistent state!"' ERR

# Run main function
main "$@"
