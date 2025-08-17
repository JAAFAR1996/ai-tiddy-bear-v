#!/bin/bash

# AI Teddy Bear Database Backup Script
# Usage: ./backup.sh [backup_type] [retention_days]

set -e

# Configuration
BACKUP_TYPE=${1:-full}  # full, incremental, schema-only
RETENTION_DAYS=${2:-30}
BACKUP_DIR="/backups/ai-teddy-bear"
LOG_FILE="/var/log/ai-teddy-backup.log"
ENCRYPTION_KEY_FILE="/etc/ai-teddy/backup.key"

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

# Create backup directory structure
setup_backup_directory() {
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="$BACKUP_DIR/$TIMESTAMP"
    
    mkdir -p "$BACKUP_PATH"
    mkdir -p "$BACKUP_DIR/logs"
    
    log "Backup directory created: $BACKUP_PATH"
}

# Database backup functions
backup_database() {
    log "Starting database backup (type: $BACKUP_TYPE)..."
    
    case $BACKUP_TYPE in
        "full")
            backup_full_database
            ;;
        "incremental")
            backup_incremental_database
            ;;
        "schema-only")
            backup_schema_only
            ;;
        *)
            error "Invalid backup type: $BACKUP_TYPE"
            ;;
    esac
}

backup_full_database() {
    log "Creating full database backup..."
    
    # Full database dump with custom format for better compression
    BACKUP_FILE="$BACKUP_PATH/database_full.dump"
    
    if docker-compose exec -T postgres pg_dump \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --format=custom \
        --compress=9 \
        --verbose \
        --file=/tmp/backup.dump 2>> "$LOG_FILE"; then
        
        # Copy backup from container
        docker cp $(docker-compose ps -q postgres):/tmp/backup.dump "$BACKUP_FILE"
        
        # Verify backup integrity
        if docker-compose exec -T postgres pg_restore --list /tmp/backup.dump > /dev/null 2>&1; then
            success "Full database backup completed and verified"
        else
            error "Backup verification failed"
        fi
        
        # Clean up temporary file
        docker-compose exec -T postgres rm -f /tmp/backup.dump
    else
        error "Failed to create database backup"
    fi
}

backup_incremental_database() {
    log "Creating incremental database backup..."
    
    # Get last backup LSN (Log Sequence Number)
    LAST_BACKUP_LSN_FILE="$BACKUP_DIR/last_backup_lsn"
    
    if [ -f "$LAST_BACKUP_LSN_FILE" ]; then
        LAST_LSN=$(cat "$LAST_BACKUP_LSN_FILE")
        log "Last backup LSN: $LAST_LSN"
    else
        warning "No previous backup found, performing full backup instead"
        backup_full_database
        return
    fi
    
    # Create WAL archive backup
    BACKUP_FILE="$BACKUP_PATH/database_incremental.tar.gz"
    
    if docker-compose exec -T postgres tar -czf /tmp/wal_backup.tar.gz -C /var/lib/postgresql/data pg_wal/; then
        docker cp $(docker-compose ps -q postgres):/tmp/wal_backup.tar.gz "$BACKUP_FILE"
        success "Incremental backup completed"
        
        # Update LSN
        CURRENT_LSN=$(docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT pg_current_wal_lsn();" | tr -d ' ')
        echo "$CURRENT_LSN" > "$LAST_BACKUP_LSN_FILE"
        
        # Clean up
        docker-compose exec -T postgres rm -f /tmp/wal_backup.tar.gz
    else
        error "Failed to create incremental backup"
    fi
}

backup_schema_only() {
    log "Creating schema-only backup..."
    
    BACKUP_FILE="$BACKUP_PATH/database_schema.sql"
    
    if docker-compose exec -T postgres pg_dump \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --schema-only \
        --no-owner \
        --no-privileges > "$BACKUP_FILE" 2>> "$LOG_FILE"; then
        success "Schema backup completed"
    else
        error "Failed to create schema backup"
    fi
}

# Application data backup
backup_application_data() {
    log "Backing up application data..."
    
    # Backup logs
    if [ -d "./logs" ]; then
        tar -czf "$BACKUP_PATH/logs.tar.gz" ./logs
        log "Logs backed up"
    fi
    
    # Backup application data directory
    if [ -d "./data" ]; then
        tar -czf "$BACKUP_PATH/app_data.tar.gz" ./data
        log "Application data backed up"
    fi
    
    # Backup configuration files
    tar -czf "$BACKUP_PATH/config.tar.gz" \
        --exclude='.env*' \
        --exclude='*.key' \
        --exclude='*.pem' \
        docker-compose.yml \
        Dockerfile \
        alembic.ini \
        nginx/ \
        scripts/ 2>/dev/null || true
    
    log "Configuration files backed up"
}

# Encrypt backup files
encrypt_backup() {
    if [ -f "$ENCRYPTION_KEY_FILE" ]; then
        log "Encrypting backup files..."
        
        for file in "$BACKUP_PATH"/*; do
            if [ -f "$file" ] && [[ ! "$file" == *.enc ]]; then
                openssl enc -aes-256-cbc -salt -pbkdf2 -in "$file" -out "$file.enc" -pass file:"$ENCRYPTION_KEY_FILE"
                rm "$file"
                log "Encrypted: $(basename "$file")"
            fi
        done
        
        success "Backup encryption completed"
    else
        warning "Encryption key not found, skipping encryption"
    fi
}

# Compress final backup
compress_backup() {
    log "Compressing backup archive..."
    
    FINAL_BACKUP="$BACKUP_DIR/ai-teddy-backup-$(date +%Y%m%d_%H%M%S).tar.gz"
    
    if tar -czf "$FINAL_BACKUP" -C "$BACKUP_DIR" "$(basename "$BACKUP_PATH")"; then
        # Remove uncompressed backup directory
        rm -rf "$BACKUP_PATH"
        
        # Calculate and log backup size
        BACKUP_SIZE=$(du -h "$FINAL_BACKUP" | cut -f1)
        success "Backup compressed: $FINAL_BACKUP ($BACKUP_SIZE)"
        
        # Create checksum
        sha256sum "$FINAL_BACKUP" > "$FINAL_BACKUP.sha256"
        log "Checksum created: $FINAL_BACKUP.sha256"
    else
        error "Failed to compress backup"
    fi
}

# Upload to remote storage (optional)
upload_backup() {
    if [ -n "$BACKUP_REMOTE_PATH" ]; then
        log "Uploading backup to remote storage..."
        
        # Example: Upload to S3 (uncomment and configure as needed)
        # aws s3 cp "$FINAL_BACKUP" "$BACKUP_REMOTE_PATH/"
        # aws s3 cp "$FINAL_BACKUP.sha256" "$BACKUP_REMOTE_PATH/"
        
        log "Remote upload would be performed here"
    fi
}

# Clean old backups
cleanup_old_backups() {
    log "Cleaning up old backups (retention: $RETENTION_DAYS days)..."
    
    # Remove backups older than retention period
    find "$BACKUP_DIR" -name "ai-teddy-backup-*.tar.gz" -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR" -name "*.sha256" -mtime +$RETENTION_DAYS -delete
    
    # Count remaining backups
    REMAINING_BACKUPS=$(find "$BACKUP_DIR" -name "ai-teddy-backup-*.tar.gz" | wc -l)
    success "Cleanup completed. Remaining backups: $REMAINING_BACKUPS"
}

# Generate backup report
generate_report() {
    REPORT_FILE="$BACKUP_DIR/logs/backup-report-$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$REPORT_FILE" << EOF
AI Teddy Bear Backup Report
===========================

Backup Date: $(date)
Backup Type: $BACKUP_TYPE
Retention Days: $RETENTION_DAYS

Backup Location: $FINAL_BACKUP
Backup Size: $(du -h "$FINAL_BACKUP" 2>/dev/null | cut -f1 || echo "Unknown")

Database Backup: $([ -f "$BACKUP_PATH/database_full.dump" ] || [ -f "$BACKUP_PATH/database_incremental.tar.gz" ] || [ -f "$BACKUP_PATH/database_schema.sql" ] && echo "Success" || echo "Failed")
Application Data: $([ -f "$BACKUP_PATH/app_data.tar.gz" ] && echo "Success" || echo "Skipped")
Configuration: $([ -f "$BACKUP_PATH/config.tar.gz" ] && echo "Success" || echo "Failed")

Total Backup Size: $(du -sh "$BACKUP_DIR" | cut -f1)
Available Disk Space: $(df -h "$BACKUP_DIR" | awk 'NR==2{print $4}')

Status: Completed Successfully
EOF

    log "Backup report generated: $REPORT_FILE"
}

# Main backup function
main() {
    log "Starting backup process..."
    log "Backup type: $BACKUP_TYPE"
    log "Retention days: $RETENTION_DAYS"
    
    load_environment
    setup_backup_directory
    backup_database
    backup_application_data
    encrypt_backup
    compress_backup
    upload_backup
    cleanup_old_backups
    generate_report
    
    success "Backup process completed successfully!"
}

# Error handling
trap 'error "Backup failed at line $LINENO"' ERR

# Run main function
main "$@"
