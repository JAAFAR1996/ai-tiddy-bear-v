#!/bin/bash
# Health check script for backup services
# Verifies all critical backup services are running and healthy

set -e

# Configuration
HEALTH_CHECK_TIMEOUT=30
LOG_FILE="/app/logs/healthcheck.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Logging function
log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

# Check if supervisor is running
check_supervisor() {
    if ! pgrep -f supervisord > /dev/null; then
        log "ERROR: supervisord is not running"
        return 1
    fi
    log "INFO: supervisord is running"
    return 0
}

# Check backup orchestrator service
check_backup_orchestrator() {
    if ! supervisorctl status backup-orchestrator | grep -q "RUNNING"; then
        log "ERROR: backup-orchestrator service is not running"
        return 1
    fi
    log "INFO: backup-orchestrator service is healthy"
    return 0
}

# Check backup scheduler service
check_backup_scheduler() {
    if ! supervisorctl status backup-scheduler | grep -q "RUNNING"; then
        log "ERROR: backup-scheduler service is not running"
        return 1
    fi
    log "INFO: backup-scheduler service is healthy"
    return 0
}

# Check backup monitor service
check_backup_monitor() {
    if ! supervisorctl status backup-monitor | grep -q "RUNNING"; then
        log "ERROR: backup-monitor service is not running"
        return 1
    fi
    log "INFO: backup-monitor service is healthy"
    return 0
}

# Check metrics exporter
check_metrics_exporter() {
    if ! supervisorctl status metrics-exporter | grep -q "RUNNING"; then
        log "ERROR: metrics-exporter service is not running"
        return 1
    fi
    
    # Check if metrics endpoint is responding
    if ! curl -s -f http://localhost:9090/metrics > /dev/null; then
        log "ERROR: metrics endpoint is not responding"
        return 1
    fi
    
    log "INFO: metrics-exporter service is healthy"
    return 0
}

# Check disk space
check_disk_space() {
    BACKUP_DIR="/app/backups"
    AVAILABLE_SPACE=$(df "$BACKUP_DIR" | awk 'NR==2 {print $4}')
    AVAILABLE_GB=$((AVAILABLE_SPACE / 1024 / 1024))
    
    if [ "$AVAILABLE_GB" -lt 5 ]; then
        log "ERROR: Low disk space: ${AVAILABLE_GB}GB available"
        return 1
    fi
    
    log "INFO: Disk space is adequate: ${AVAILABLE_GB}GB available"
    return 0
}

# Check database connectivity
check_database_connectivity() {
    if [ -n "$DATABASE_URL" ]; then
        # Extract database connection details
        DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\).*/\1/p')
        DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
        
        if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
            if ! timeout 5 bash -c "echo > /dev/tcp/$DB_HOST/$DB_PORT"; then
                log "ERROR: Cannot connect to database at $DB_HOST:$DB_PORT"
                return 1
            fi
            log "INFO: Database connectivity is healthy"
        else
            log "WARNING: Could not parse database connection details"
        fi
    else
        log "WARNING: DATABASE_URL not set, skipping database connectivity check"
    fi
    return 0
}

# Check storage providers
check_storage_providers() {
    # Check if required environment variables are set
    if [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
        log "INFO: AWS credentials are configured"
    fi
    
    if [ -n "$AZURE_STORAGE_CONNECTION_STRING" ]; then
        log "INFO: Azure storage is configured"
    fi
    
    # Always assume at least local storage is available
    if [ -d "/app/backups" ] && [ -w "/app/backups" ]; then
        log "INFO: Local storage is available and writable"
    else
        log "ERROR: Local backup directory is not writable"
        return 1
    fi
    
    return 0
}

# Check log files
check_log_files() {
    LOG_DIR="/app/logs"
    
    if [ ! -d "$LOG_DIR" ]; then
        log "ERROR: Log directory does not exist"
        return 1
    fi
    
    if [ ! -w "$LOG_DIR" ]; then
        log "ERROR: Log directory is not writable"
        return 1
    fi
    
    log "INFO: Log directory is healthy"
    return 0
}

# Main health check function
main() {
    log "Starting health check..."
    
    local exit_code=0
    
    # Run all health checks
    check_supervisor || exit_code=1
    check_backup_orchestrator || exit_code=1
    check_backup_scheduler || exit_code=1
    check_backup_monitor || exit_code=1
    check_metrics_exporter || exit_code=1
    check_disk_space || exit_code=1
    check_database_connectivity || exit_code=1
    check_storage_providers || exit_code=1
    check_log_files || exit_code=1
    
    if [ $exit_code -eq 0 ]; then
        log "Health check passed: All services are healthy"
    else
        log "Health check failed: One or more services are unhealthy"
    fi
    
    return $exit_code
}

# Run health check with timeout
timeout $HEALTH_CHECK_TIMEOUT main

exit $?