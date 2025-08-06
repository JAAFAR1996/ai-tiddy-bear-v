#!/bin/bash
# AI Teddy Bear Production Database Restore Script
# COPPA compliant restore with safety checks

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/backups}"

# Database configuration
DB_HOST="${PGHOST:-postgres}"
DB_PORT="${PGPORT:-5432}"
DB_NAME="${PGDATABASE:-ai_teddy_bear}"
DB_USER="${PGUSER:-ai_teddy_user}"

# Encryption key for COPPA compliance
BACKUP_ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"

# Logging
LOG_FILE="${BACKUP_DIR}/restore.log"

# Functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

error_exit() {
    log "ERROR: $1"
    exit 1
}

usage() {
    cat << EOF
Usage: $0 [OPTIONS] BACKUP_FILE

Restore AI Teddy Bear database from backup

OPTIONS:
    -h, --help          Show this help message
    -f, --force         Skip confirmation prompts
    -d, --dry-run       Show what would be done without executing
    --no-create         Don't recreate database (restore into existing)
    --verify-only       Only verify backup integrity

EXAMPLES:
    $0 ai_teddy_backup_20231215_140000.sql.enc
    $0 --dry-run ai_teddy_backup_20231215_140000.sql
    $0 --force --no-create backup.sql.enc

EOF
}

verify_backup() {
    local backup_file="$1"
    local temp_file=""
    
    log "Verifying backup integrity..."
    
    # Check if file exists
    if [[ ! -f "${backup_file}" ]]; then
        error_exit "Backup file not found: ${backup_file}"
    fi
    
    # Check if encrypted
    if [[ "${backup_file}" == *.enc ]]; then
        if [[ -z "${BACKUP_ENCRYPTION_KEY}" ]]; then
            error_exit "Encrypted backup requires BACKUP_ENCRYPTION_KEY"
        fi
        
        log "Verifying encrypted backup..."
        temp_file="/tmp/restore_verify_$$.sql"
        
        if ! openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
            -in "${backup_file}" \
            -pass pass:"${BACKUP_ENCRYPTION_KEY}" \
            -out "${temp_file}"; then
            error_exit "Failed to decrypt backup file"
        fi
        
        backup_file="${temp_file}"
    fi
    
    # Verify PostgreSQL dump
    if ! pg_restore --list "${backup_file}" > /dev/null 2>&1; then
        [[ -n "${temp_file}" ]] && rm -f "${temp_file}"
        error_exit "Invalid PostgreSQL backup file"
    fi
    
    log "Backup verification successful"
    
    # Clean up temp file
    [[ -n "${temp_file}" ]] && rm -f "${temp_file}"
    
    return 0
}

create_pre_restore_backup() {
    log "Creating pre-restore backup of current database..."
    
    local pre_restore_backup="${BACKUP_DIR}/pre_restore_$(date +%Y%m%d_%H%M%S).sql"
    
    if pg_dump \
        -h "${DB_HOST}" \
        -p "${DB_PORT}" \
        -U "${DB_USER}" \
        -d "${DB_NAME}" \
        --format=custom \
        --compress=9 \
        --file="${pre_restore_backup}"; then
        log "Pre-restore backup created: ${pre_restore_backup}"
        echo "${pre_restore_backup}"
    else
        log "WARNING: Failed to create pre-restore backup"
        echo ""
    fi
}

restore_database() {
    local backup_file="$1"
    local force="$2"
    local dry_run="$3"
    local no_create="$4"
    local temp_file=""
    
    # Verify backup first
    verify_backup "${backup_file}" || error_exit "Backup verification failed"
    
    # Handle encrypted backups
    if [[ "${backup_file}" == *.enc ]]; then
        log "Decrypting backup file..."
        temp_file="/tmp/restore_$$.sql"
        
        if ! openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
            -in "${backup_file}" \
            -pass pass:"${BACKUP_ENCRYPTION_KEY}" \
            -out "${temp_file}"; then
            error_exit "Failed to decrypt backup file"
        fi
        
        backup_file="${temp_file}"
    fi
    
    # Check database connectivity
    log "Checking database connectivity..."
    if ! pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; then
        error_exit "Cannot connect to database server ${DB_HOST}:${DB_PORT}"
    fi
    
    # Show restore plan
    log "Restore Plan:"
    log "  Source: ${backup_file}"
    log "  Target: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
    log "  User: ${DB_USER}"
    log "  Recreate DB: $([ "${no_create}" = "true" ] && echo "No" || echo "Yes")"
    log "  Encrypted: $([ -n "${temp_file}" ] && echo "Yes" || echo "No")"
    
    if [[ "${dry_run}" = "true" ]]; then
        log "DRY RUN: Would restore database with above configuration"
        [[ -n "${temp_file}" ]] && rm -f "${temp_file}"
        return 0
    fi
    
    # Confirmation
    if [[ "${force}" != "true" ]]; then
        echo
        echo "⚠️  WARNING: This will replace the current database content!"
        echo "   Database: ${DB_NAME}"
        echo "   Host: ${DB_HOST}"
        echo
        read -p "Are you sure you want to continue? (yes/no): " -r
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            log "Restore cancelled by user"
            [[ -n "${temp_file}" ]] && rm -f "${temp_file}"
            exit 0
        fi
    fi
    
    # Create pre-restore backup
    local pre_restore_backup=""
    if [[ "${no_create}" = "true" ]]; then
        pre_restore_backup=$(create_pre_restore_backup)
    fi
    
    # Start restore process
    log "Starting database restore..."
    
    # Drop existing connections to the database
    log "Terminating existing database connections..."
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();" \
        || log "WARNING: Could not terminate all connections"
    
    # Restore database
    local restore_options=(
        --host="${DB_HOST}"
        --port="${DB_PORT}"
        --username="${DB_USER}"
        --dbname="${DB_NAME}"
        --verbose
        --clean
        --if-exists
        --no-password
    )
    
    if [[ "${no_create}" != "true" ]]; then
        restore_options+=(--create)
    fi
    
    if pg_restore "${restore_options[@]}" "${backup_file}"; then
        log "Database restore completed successfully"
        
        # Verify restore
        log "Verifying restored database..."
        if psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT COUNT(*) FROM information_schema.tables;" > /dev/null 2>&1; then
            log "Database verification successful"
        else
            log "WARNING: Database verification failed"
        fi
        
        # Show restore summary
        local table_count=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | xargs || echo "unknown")
        log "Restore Summary:"
        log "  Tables restored: ${table_count}"
        log "  Pre-restore backup: ${pre_restore_backup:-"Not created"}"
        
    else
        error_exit "Database restore failed"
    fi
    
    # Clean up temp file
    [[ -n "${temp_file}" ]] && rm -f "${temp_file}"
    
    # Send notification (if configured)
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data '{"text":"✅ AI Teddy Bear database restore completed successfully\nDatabase: '"${DB_NAME}"'\nTables: '"${table_count}"'"}' \
            "${SLACK_WEBHOOK_URL}" || log "Failed to send Slack notification"
    fi
}

# Main function
main() {
    local backup_file=""
    local force=false
    local dry_run=false
    local no_create=false
    local verify_only=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -f|--force)
                force=true
                shift
                ;;
            -d|--dry-run)
                dry_run=true
                shift
                ;;
            --no-create)
                no_create=true
                shift
                ;;
            --verify-only)
                verify_only=true
                shift
                ;;
            -*)
                error_exit "Unknown option: $1"
                ;;
            *)
                if [[ -z "${backup_file}" ]]; then
                    backup_file="$1"
                else
                    error_exit "Multiple backup files specified"
                fi
                shift
                ;;
        esac
    done
    
    # Validate arguments
    if [[ -z "${backup_file}" ]]; then
        error_exit "No backup file specified. Use --help for usage information."
    fi
    
    # Convert relative path to absolute
    if [[ ! "${backup_file}" = /* ]]; then
        backup_file="${BACKUP_DIR}/${backup_file}"
    fi
    
    log "AI Teddy Bear Database Restore Starting..."
    log "Backup file: ${backup_file}"
    
    # Create log directory
    mkdir -p "${BACKUP_DIR}"
    
    if [[ "${verify_only}" = "true" ]]; then
        verify_backup "${backup_file}"
        log "Backup verification completed successfully"
    else
        restore_database "${backup_file}" "${force}" "${dry_run}" "${no_create}"
        log "Database restore process completed"
    fi
}

# Run main function
main "$@"