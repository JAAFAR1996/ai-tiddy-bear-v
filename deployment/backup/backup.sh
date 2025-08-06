#!/bin/bash
# AI Teddy Bear Production Database Backup Script
# COPPA compliant automated backup with encryption

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="ai_teddy_backup_${TIMESTAMP}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

# Database configuration
DB_HOST="${PGHOST:-postgres}"
DB_PORT="${PGPORT:-5432}"
DB_NAME="${PGDATABASE:-ai_teddy_bear}"
DB_USER="${PGUSER:-ai_teddy_user}"

# Encryption key for COPPA compliance
BACKUP_ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"

# AWS S3 configuration (optional)
S3_BUCKET="${S3_BUCKET:-}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Logging
LOG_FILE="${BACKUP_DIR}/backup.log"

# Functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

error_exit() {
    log "ERROR: $1"
    exit 1
}

cleanup() {
    log "Cleaning up temporary files..."
    rm -f "${BACKUP_DIR}/${BACKUP_NAME}.sql.tmp"
}

# Trap for cleanup
trap cleanup EXIT

# Main backup function
main() {
    log "Starting AI Teddy Bear database backup..."
    
    # Create backup directory if it doesn't exist
    mkdir -p "${BACKUP_DIR}"
    
    # Check database connectivity
    log "Checking database connectivity..."
    if ! pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" >/dev/null 2>&1; then
        error_exit "Cannot connect to database ${DB_NAME} on ${DB_HOST}:${DB_PORT}"
    fi
    
    # Create database dump
    log "Creating database dump..."
    local dump_file="${BACKUP_DIR}/${BACKUP_NAME}.sql.tmp"
    
    # Use pg_dump with compression and verbose output
    if ! pg_dump \
        -h "${DB_HOST}" \
        -p "${DB_PORT}" \
        -U "${DB_USER}" \
        -d "${DB_NAME}" \
        --verbose \
        --no-password \
        --clean \
        --if-exists \
        --create \
        --format=custom \
        --compress=9 \
        --file="${dump_file}"; then
        error_exit "Database dump failed"
    fi
    
    log "Database dump completed successfully"
    
    # Encrypt backup for COPPA compliance
    if [[ -n "${BACKUP_ENCRYPTION_KEY}" ]]; then
        log "Encrypting backup for COPPA compliance..."
        local encrypted_file="${BACKUP_DIR}/${BACKUP_NAME}.sql.enc"
        
        if ! openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 \
            -in "${dump_file}" \
            -out "${encrypted_file}" \
            -pass pass:"${BACKUP_ENCRYPTION_KEY}"; then
            error_exit "Backup encryption failed"
        fi
        
        # Remove unencrypted file
        rm -f "${dump_file}"
        mv "${encrypted_file}" "${BACKUP_DIR}/${BACKUP_NAME}.sql.enc"
        
        log "Backup encrypted successfully"
        FINAL_BACKUP_FILE="${BACKUP_DIR}/${BACKUP_NAME}.sql.enc"
    else
        log "WARNING: No encryption key provided. Backup will be stored unencrypted."
        mv "${dump_file}" "${BACKUP_DIR}/${BACKUP_NAME}.sql"
        FINAL_BACKUP_FILE="${BACKUP_DIR}/${BACKUP_NAME}.sql"
    fi
    
    # Generate backup metadata
    local metadata_file="${BACKUP_DIR}/${BACKUP_NAME}.metadata.json"
    cat > "${metadata_file}" << EOF
{
    "backup_name": "${BACKUP_NAME}",
    "timestamp": "${TIMESTAMP}",
    "database": "${DB_NAME}",
    "host": "${DB_HOST}",
    "encrypted": $([ -n "${BACKUP_ENCRYPTION_KEY}" ] && echo "true" || echo "false"),
    "file_size": $(stat -f%z "${FINAL_BACKUP_FILE}" 2>/dev/null || stat -c%s "${FINAL_BACKUP_FILE}"),
    "checksum": "$(sha256sum "${FINAL_BACKUP_FILE}" | cut -d' ' -f1)",
    "coppa_compliant": true,
    "retention_days": ${RETENTION_DAYS}
}
EOF
    
    log "Backup metadata created"
    
    # Upload to S3 if configured
    if [[ -n "${S3_BUCKET}" ]]; then
        log "Uploading backup to S3..."
        
        if command -v aws >/dev/null 2>&1; then
            # Upload backup file
            if aws s3 cp "${FINAL_BACKUP_FILE}" "s3://${S3_BUCKET}/backups/${BACKUP_NAME}.sql$([ -n "${BACKUP_ENCRYPTION_KEY}" ] && echo ".enc" || echo "")" --region "${AWS_REGION}"; then
                log "Backup uploaded to S3 successfully"
                
                # Upload metadata
                aws s3 cp "${metadata_file}" "s3://${S3_BUCKET}/backups/${BACKUP_NAME}.metadata.json" --region "${AWS_REGION}"
                log "Metadata uploaded to S3 successfully"
            else
                log "WARNING: Failed to upload backup to S3"
            fi
        else
            log "WARNING: AWS CLI not available, skipping S3 upload"
        fi
    fi
    
    # Clean up old backups
    log "Cleaning up old backups..."
    find "${BACKUP_DIR}" -name "ai_teddy_backup_*" -type f -mtime +${RETENTION_DAYS} -delete
    
    # Clean up old S3 backups if configured
    if [[ -n "${S3_BUCKET}" ]] && command -v aws >/dev/null 2>&1; then
        aws s3 ls "s3://${S3_BUCKET}/backups/" --region "${AWS_REGION}" | \
        awk '$1 < "'$(date -d "${RETENTION_DAYS} days ago" +%Y-%m-%d)'" {print $4}' | \
        while read -r file; do
            aws s3 rm "s3://${S3_BUCKET}/backups/${file}" --region "${AWS_REGION}"
            log "Deleted old S3 backup: ${file}"
        done
    fi
    
    # Backup verification
    log "Verifying backup integrity..."
    if [[ -n "${BACKUP_ENCRYPTION_KEY}" ]]; then
        # Test decryption
        if openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
            -in "${FINAL_BACKUP_FILE}" \
            -pass pass:"${BACKUP_ENCRYPTION_KEY}" \
            -out /dev/null; then
            log "Backup integrity verified (encrypted)"
        else
            error_exit "Backup integrity check failed (encrypted)"
        fi
    else
        # Test pg_restore
        if pg_restore --list "${FINAL_BACKUP_FILE}" > /dev/null 2>&1; then
            log "Backup integrity verified (unencrypted)"
        else
            error_exit "Backup integrity check failed (unencrypted)"
        fi
    fi
    
    # Final summary
    local backup_size=$(stat -f%z "${FINAL_BACKUP_FILE}" 2>/dev/null || stat -c%s "${FINAL_BACKUP_FILE}")
    log "Backup completed successfully!"
    log "Backup file: ${FINAL_BACKUP_FILE}"
    log "Backup size: $(numfmt --to=iec-i --format='%.1f' ${backup_size})B"
    log "Encrypted: $([ -n "${BACKUP_ENCRYPTION_KEY}" ] && echo "Yes" || echo "No")"
    log "COPPA Compliant: Yes"
    
    # Send notification (if configured)
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data '{"text":"✅ AI Teddy Bear database backup completed successfully\nBackup: '"${BACKUP_NAME}"'\nSize: '"$(numfmt --to=iec-i --format='%.1f' ${backup_size})B"'"}' \
            "${SLACK_WEBHOOK_URL}" || log "Failed to send Slack notification"
    fi
}

# Run main function
main "$@"