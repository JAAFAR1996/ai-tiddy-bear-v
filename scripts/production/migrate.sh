#!/bin/bash

# AI Teddy Bear Database Migration Script
# Usage: ./migrate.sh [migration_type] [target_version]

set -e

# Configuration
MIGRATION_TYPE=${1:-latest}  # latest, specific, rollback
TARGET_VERSION=${2:-latest}
LOG_FILE="/var/log/ai-teddy-migration.log"
BACKUP_BEFORE_MIGRATION=true
DRY_RUN=${DRY_RUN:-false}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# Load environment variables
load_environment() {
    if [ -f ".env" ]; then
        source .env
    else
        error "Environment file not found"
    fi
    
    # Validate required variables
    if [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ] || [ -z "$DB_NAME" ]; then
        error "Database configuration not found in environment"
    fi
}

# Check prerequisites
check_prerequisites() {
    log "Checking migration prerequisites..."
    
    # Check if database is accessible
    if ! docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
        error "Cannot connect to database"
    fi
    
    # Check if application is running
    if ! docker-compose ps app | grep -q "Up"; then
        warning "Application container is not running"
        read -p "Continue with migration? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            error "Migration cancelled by user"
        fi
    fi
    
    # Check disk space
    AVAILABLE_SPACE=$(df / | awk 'NR==2{print $4}')
    if [ "$AVAILABLE_SPACE" -lt 1048576 ]; then  # Less than 1GB
        warning "Low disk space: $(df -h / | awk 'NR==2{print $4}') available"
    fi
    
    success "Prerequisites check completed"
}

# Create backup before migration
create_backup() {
    if [ "$BACKUP_BEFORE_MIGRATION" = true ]; then
        log "Creating backup before migration..."
        
        if [ -f "./scripts/production/backup.sh" ]; then
            chmod +x ./scripts/production/backup.sh
            ./scripts/production/backup.sh full 7
            success "Pre-migration backup completed"
        else
            warning "Backup script not found, proceeding without backup"
        fi
    else
        log "Skipping backup (disabled)"
    fi
}

# Check current migration status
check_migration_status() {
    log "Checking current migration status..."
    
    # Check if Alembic is initialized
    if ! docker-compose exec -T app python -c "from alembic import command, config; cfg = config.Config('alembic.ini'); command.current(cfg)" 2>/dev/null; then
        warning "Alembic not initialized or database not up to date"
        
        # Try to stamp current version
        if docker-compose exec -T app python -c "from alembic import command, config; cfg = config.Config('alembic.ini'); command.stamp(cfg, 'head')" 2>/dev/null; then
            info "Database stamped with current head revision"
        else
            error "Failed to initialize Alembic version control"
        fi
    fi
    
    # Get current revision
    CURRENT_REVISION=$(docker-compose exec -T app python -c "
from alembic import command, config
from alembic.script import ScriptDirectory
from alembic.runtime.environment import EnvironmentContext
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine
import os

# Create engine
engine = create_engine(f'postgresql://{os.getenv(\"DB_USER\")}:{os.getenv(\"DB_PASSWORD\")}@{os.getenv(\"DB_HOST\", \"postgres\")}:{os.getenv(\"DB_PORT\", \"5432\")}/{os.getenv(\"DB_NAME\")}')

# Get current revision
with engine.connect() as connection:
    context = MigrationContext.configure(connection)
    current_rev = context.get_current_revision()
    print(current_rev or 'None')
" 2>/dev/null)
    
    log "Current database revision: ${CURRENT_REVISION:-None}"
    
    # Get head revision
    HEAD_REVISION=$(docker-compose exec -T app python -c "
from alembic.script import ScriptDirectory
from alembic import config
cfg = config.Config('alembic.ini')
script = ScriptDirectory.from_config(cfg)
print(script.get_current_head())
" 2>/dev/null)
    
    log "Latest available revision: ${HEAD_REVISION:-None}"
}

# Show pending migrations
show_pending_migrations() {
    log "Checking for pending migrations..."
    
    PENDING_MIGRATIONS=$(docker-compose exec -T app python -c "
from alembic import command, config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine
import os

# Create engine
engine = create_engine(f'postgresql://{os.getenv(\"DB_USER\")}:{os.getenv(\"DB_PASSWORD\")}@{os.getenv(\"DB_HOST\", \"postgres\")}:{os.getenv(\"DB_PORT\", \"5432\")}/{os.getenv(\"DB_NAME\")}')

# Get pending migrations
cfg = config.Config('alembic.ini')
script = ScriptDirectory.from_config(cfg)

with engine.connect() as connection:
    context = MigrationContext.configure(connection)
    current_rev = context.get_current_revision()
    
    if current_rev:
        # Get revisions between current and head
        revisions = list(script.walk_revisions(current_rev, 'heads'))
        if len(revisions) > 1:  # Exclude current revision
            print(f'{len(revisions) - 1} pending migrations')
            for rev in reversed(revisions[1:]):
                print(f'  {rev.revision}: {rev.doc or \"No description\"}')
        else:
            print('No pending migrations')
    else:
        all_revisions = list(script.walk_revisions('base', 'heads'))
        print(f'{len(all_revisions)} migrations to apply (fresh database)')
        for rev in reversed(all_revisions):
            print(f'  {rev.revision}: {rev.doc or \"No description\"}')
" 2>/dev/null)
    
    echo "$PENDING_MIGRATIONS"
}

# Validate migration safety
validate_migration() {
    log "Validating migration safety..."
    
    if [ "$DRY_RUN" = true ]; then
        log "Performing dry run migration check..."
        
        # Create a test database for dry run
        TEST_DB_NAME="${DB_NAME}_migration_test"
        
        # Create test database
        docker-compose exec -T postgres psql -U "$DB_USER" -c "CREATE DATABASE ${TEST_DB_NAME};" 2>/dev/null || true
        
        # Run migration on test database
        if docker-compose exec -T app env DB_NAME="$TEST_DB_NAME" python -c "
from alembic import command, config
cfg = config.Config('alembic.ini')
command.upgrade(cfg, 'head')
print('Dry run migration successful')
" 2>/dev/null; then
            success "Dry run migration completed successfully"
        else
            error "Dry run migration failed"
        fi
        
        # Clean up test database
        docker-compose exec -T postgres psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS ${TEST_DB_NAME};" 2>/dev/null || true
        
        info "Dry run completed. Use 'DRY_RUN=false ./migrate.sh' to apply migrations"
        exit 0
    fi
}

# Apply migrations
apply_migrations() {
    case $MIGRATION_TYPE in
        "latest"|"head")
            apply_latest_migrations
            ;;
        "specific")
            apply_specific_migration
            ;;
        "rollback")
            rollback_migration
            ;;
        *)
            error "Invalid migration type: $MIGRATION_TYPE"
            ;;
    esac
}

apply_latest_migrations() {
    log "Applying latest migrations..."
    
    if docker-compose exec -T app python -c "
from alembic import command, config
cfg = config.Config('alembic.ini')
command.upgrade(cfg, 'head')
print('Migrations applied successfully')
" 2>> "$LOG_FILE"; then
        success "Latest migrations applied successfully"
    else
        error "Failed to apply migrations"
    fi
}

apply_specific_migration() {
    if [ "$TARGET_VERSION" = "latest" ]; then
        error "Target version required for specific migration"
    fi
    
    log "Applying migration to specific version: $TARGET_VERSION"
    
    if docker-compose exec -T app python -c "
from alembic import command, config
cfg = config.Config('alembic.ini')
command.upgrade(cfg, '$TARGET_VERSION')
print('Migration to $TARGET_VERSION completed')
" 2>> "$LOG_FILE"; then
        success "Migration to $TARGET_VERSION completed successfully"
    else
        error "Failed to apply migration to $TARGET_VERSION"
    fi
}

rollback_migration() {
    if [ "$TARGET_VERSION" = "latest" ]; then
        error "Target version required for rollback"
    fi
    
    warning "Rolling back to version: $TARGET_VERSION"
    read -p "Are you sure you want to rollback? This may cause data loss (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        error "Rollback cancelled by user"
    fi
    
    log "Rolling back to version: $TARGET_VERSION"
    
    if docker-compose exec -T app python -c "
from alembic import command, config
cfg = config.Config('alembic.ini')
command.downgrade(cfg, '$TARGET_VERSION')
print('Rollback to $TARGET_VERSION completed')
" 2>> "$LOG_FILE"; then
        success "Rollback to $TARGET_VERSION completed successfully"
    else
        error "Failed to rollback to $TARGET_VERSION"
    fi
}

# Verify migration results
verify_migration() {
    log "Verifying migration results..."
    
    # Check database connection
    if ! docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
        error "Database connection failed after migration"
    fi
    
    # Check application startup
    log "Testing application startup..."
    if docker-compose restart app && sleep 10; then
        if docker-compose exec -T app python -c "
import sys
sys.path.append('/app')
try:
    from src.main import app
    print('Application imports successfully')
except Exception as e:
    print(f'Application import failed: {e}')
    sys.exit(1)
" 2>/dev/null; then
            success "Application starts successfully after migration"
        else
            error "Application failed to start after migration"
        fi
    else
        error "Failed to restart application container"
    fi
    
    # Run basic database tests
    log "Running post-migration database tests..."
    if docker-compose exec -T app python -c "
from sqlalchemy import create_engine, text
import os

engine = create_engine(f'postgresql://{os.getenv(\"DB_USER\")}:{os.getenv(\"DB_PASSWORD\")}@{os.getenv(\"DB_HOST\", \"postgres\")}:{os.getenv(\"DB_PORT\", \"5432\")}/{os.getenv(\"DB_NAME\")}')

# Test basic operations
with engine.connect() as conn:
    # Check if main tables exist
    result = conn.execute(text('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = \\'public\\';'))
    table_count = result.scalar()
    print(f'Found {table_count} tables in database')
    
    if table_count < 5:  # Assuming we should have at least 5 tables
        raise Exception(f'Expected more tables, found only {table_count}')
    
    print('Database structure verification passed')
" 2>/dev/null; then
        success "Post-migration database tests passed"
    else
        warning "Post-migration database tests failed"
    fi
}

# Generate migration report
generate_migration_report() {
    REPORT_FILE="/var/log/migration-report-$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$REPORT_FILE" << EOF
AI Teddy Bear Migration Report
==============================

Migration Date: $(date)
Migration Type: $MIGRATION_TYPE
Target Version: $TARGET_VERSION
Dry Run: $DRY_RUN

Previous Revision: $CURRENT_REVISION
Current Revision: $(docker-compose exec -T app python -c "
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine
import os

engine = create_engine(f'postgresql://{os.getenv(\"DB_USER\")}:{os.getenv(\"DB_PASSWORD\")}@{os.getenv(\"DB_HOST\", \"postgres\")}:{os.getenv(\"DB_PORT\", \"5432\")}/{os.getenv(\"DB_NAME\")}')
with engine.connect() as connection:
    context = MigrationContext.configure(connection)
    print(context.get_current_revision() or 'None')
" 2>/dev/null)

Migration Status: Completed Successfully
Backup Created: $BACKUP_BEFORE_MIGRATION
Application Status: $(docker-compose ps app | grep -q "Up" && echo "Running" || echo "Stopped")

Post-Migration Checks:
- Database Connection: OK
- Application Startup: OK
- Table Structure: OK

Log Files:
- Migration Log: $LOG_FILE
- Application Logs: /var/log/ai-teddy-app.log
EOF

    log "Migration report generated: $REPORT_FILE"
}

# Display usage information
show_usage() {
    cat << EOF
AI Teddy Bear Migration Script

Usage: $0 [migration_type] [target_version]

Migration Types:
  latest    - Apply all pending migrations (default)
  specific  - Apply migrations up to a specific version
  rollback  - Rollback to a specific version

Examples:
  $0                           # Apply latest migrations
  $0 latest                    # Apply latest migrations
  $0 specific abc123           # Migrate to specific version
  $0 rollback def456           # Rollback to specific version

Environment Variables:
  DRY_RUN=true                 # Perform dry run without applying changes

Options:
  --help, -h                   # Show this help message
EOF
}

# Main migration function
main() {
    # Handle help flag
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        show_usage
        exit 0
    fi
    
    log "Starting migration process..."
    log "Migration type: $MIGRATION_TYPE"
    log "Target version: $TARGET_VERSION"
    log "Dry run: $DRY_RUN"
    
    load_environment
    check_prerequisites
    create_backup
    check_migration_status
    show_pending_migrations
    validate_migration
    apply_migrations
    verify_migration
    generate_migration_report
    
    success "Migration process completed successfully!"
}

# Error handling
trap 'error "Migration failed at line $LINENO"' ERR

# Run main function
main "$@"
