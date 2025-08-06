#!/bin/bash

# AI Teddy Bear Health Check Script
# Usage: ./health_check.sh [check_type] [--verbose]

set -e

# Configuration
CHECK_TYPE=${1:-all}  # all, quick, deep, monitoring
VERBOSE=${2:-false}
LOG_FILE="/var/log/ai-teddy-health.log"
HEALTH_REPORT_DIR="/var/log/health-reports"
ALERT_WEBHOOK=""  # Configure webhook URL for alerts
MAX_RESPONSE_TIME=5000  # milliseconds
MIN_DISK_SPACE=1048576  # 1GB in KB

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Health status
OVERALL_STATUS="HEALTHY"
FAILED_CHECKS=()
WARNING_CHECKS=()

# Logging functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    OVERALL_STATUS="CRITICAL"
    FAILED_CHECKS+=("$1")
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
    if [ "$OVERALL_STATUS" = "HEALTHY" ]; then
        OVERALL_STATUS="WARNING"
    fi
    WARNING_CHECKS+=("$1")
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

verbose() {
    if [ "$VERBOSE" = "--verbose" ] || [ "$VERBOSE" = "true" ]; then
        echo -e "${PURPLE}[VERBOSE]${NC} $1" | tee -a "$LOG_FILE"
    fi
}

# Load environment variables
load_environment() {
    if [ -f ".env" ]; then
        source .env
    else
        warning "Environment file not found"
    fi
}

# Check Docker and Docker Compose
check_docker() {
    log "Checking Docker environment..."
    
    # Check if Docker is running
    if ! docker version > /dev/null 2>&1; then
        error "Docker is not running or not accessible"
        return 1
    fi
    
    # Check if Docker Compose is available
    if ! docker-compose version > /dev/null 2>&1; then
        error "Docker Compose is not available"
        return 1
    fi
    
    verbose "Docker version: $(docker version --format '{{.Server.Version}}')"
    verbose "Docker Compose version: $(docker-compose version --short)"
    
    success "Docker environment check passed"
}

# Check container health
check_containers() {
    log "Checking container health..."
    
    # Get container status
    CONTAINERS=$(docker-compose ps --format "table {{.Name}}\t{{.State}}\t{{.Status}}")
    verbose "Container status:\n$CONTAINERS"
    
    # Check each service
    local services=("app" "postgres" "redis" "nginx")
    
    for service in "${services[@]}"; do
        if docker-compose ps "$service" | grep -q "Up"; then
            verbose "Service $service is running"
            
            # Check container health if health check is defined
            CONTAINER_ID=$(docker-compose ps -q "$service")
            if [ -n "$CONTAINER_ID" ]; then
                HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_ID" 2>/dev/null || echo "no-healthcheck")
                
                if [ "$HEALTH_STATUS" = "healthy" ]; then
                    verbose "Service $service health check: healthy"
                elif [ "$HEALTH_STATUS" = "unhealthy" ]; then
                    error "Service $service health check: unhealthy"
                elif [ "$HEALTH_STATUS" = "starting" ]; then
                    warning "Service $service health check: starting"
                else
                    verbose "Service $service: no health check defined"
                fi
            fi
        else
            error "Service $service is not running"
        fi
    done
    
    success "Container health check completed"
}

# Check database connectivity and performance
check_database() {
    log "Checking database health..."
    
    # Check basic connectivity
    if docker-compose exec -T postgres pg_isready -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; then
        verbose "Database connectivity: OK"
    else
        error "Database connectivity failed"
        return 1
    fi
    
    # Check database size and performance
    DB_STATS=$(docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -c "
    SELECT 
        pg_database_size('$DB_NAME') as db_size,
        (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_connections,
        (SELECT setting FROM pg_settings WHERE name = 'max_connections') as max_connections;
    " -t 2>/dev/null)
    
    if [ -n "$DB_STATS" ]; then
        DB_SIZE=$(echo "$DB_STATS" | awk '{print $1}')
        ACTIVE_CONN=$(echo "$DB_STATS" | awk '{print $2}')
        MAX_CONN=$(echo "$DB_STATS" | awk '{print $3}')
        
        verbose "Database size: $(numfmt --to=iec-i --suffix=B $DB_SIZE)"
        verbose "Active connections: $ACTIVE_CONN/$MAX_CONN"
        
        # Check connection pool usage
        CONN_USAGE=$((ACTIVE_CONN * 100 / MAX_CONN))
        if [ "$CONN_USAGE" -gt 80 ]; then
            warning "High database connection usage: ${CONN_USAGE}%"
        fi
    fi
    
    # Test query performance
    QUERY_START=$(date +%s%3N)
    docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1
    QUERY_END=$(date +%s%3N)
    QUERY_TIME=$((QUERY_END - QUERY_START))
    
    verbose "Database query response time: ${QUERY_TIME}ms"
    
    if [ "$QUERY_TIME" -gt "$MAX_RESPONSE_TIME" ]; then
        warning "Database response time is high: ${QUERY_TIME}ms"
    fi
    
    success "Database health check completed"
}

# Check Redis connectivity and performance
check_redis() {
    log "Checking Redis health..."
    
    # Check basic connectivity
    if docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
        verbose "Redis connectivity: OK"
    else
        error "Redis connectivity failed"
        return 1
    fi
    
    # Check Redis info
    REDIS_INFO=$(docker-compose exec -T redis redis-cli info server,memory,clients 2>/dev/null)
    
    if [ -n "$REDIS_INFO" ]; then
        REDIS_VERSION=$(echo "$REDIS_INFO" | grep "^redis_version:" | cut -d: -f2 | tr -d '\r')
        MEMORY_USED=$(echo "$REDIS_INFO" | grep "^used_memory_human:" | cut -d: -f2 | tr -d '\r')
        CONNECTED_CLIENTS=$(echo "$REDIS_INFO" | grep "^connected_clients:" | cut -d: -f2 | tr -d '\r')
        
        verbose "Redis version: $REDIS_VERSION"
        verbose "Memory used: $MEMORY_USED"
        verbose "Connected clients: $CONNECTED_CLIENTS"
    fi
    
    # Test Redis performance
    REDIS_START=$(date +%s%3N)
    docker-compose exec -T redis redis-cli set health_check_test "$(date)" > /dev/null 2>&1
    docker-compose exec -T redis redis-cli get health_check_test > /dev/null 2>&1
    docker-compose exec -T redis redis-cli del health_check_test > /dev/null 2>&1
    REDIS_END=$(date +%s%3N)
    REDIS_TIME=$((REDIS_END - REDIS_START))
    
    verbose "Redis operation response time: ${REDIS_TIME}ms"
    
    if [ "$REDIS_TIME" -gt "$MAX_RESPONSE_TIME" ]; then
        warning "Redis response time is high: ${REDIS_TIME}ms"
    fi
    
    success "Redis health check completed"
}

# Check application endpoints
check_application() {
    log "Checking application health..."
    
    # Wait for application to be ready
    sleep 5
    
    # Check health endpoint
    if command -v curl > /dev/null 2>&1; then
        APP_START=$(date +%s%3N)
        HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "000")
        APP_END=$(date +%s%3N)
        APP_TIME=$((APP_END - APP_START))
        
        if [ "$HTTP_STATUS" = "200" ]; then
            verbose "Application health endpoint: OK (${APP_TIME}ms)"
        else
            error "Application health endpoint failed: HTTP $HTTP_STATUS"
        fi
        
        # Check API documentation endpoint
        DOCS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs || echo "000")
        if [ "$DOCS_STATUS" = "200" ]; then
            verbose "API documentation endpoint: OK"
        else
            warning "API documentation endpoint: HTTP $DOCS_STATUS"
        fi
        
        # Check metrics endpoint if available
        METRICS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/metrics || echo "000")
        if [ "$METRICS_STATUS" = "200" ]; then
            verbose "Metrics endpoint: OK"
        else
            verbose "Metrics endpoint not available (HTTP $METRICS_STATUS)"
        fi
    else
        warning "curl not available, skipping HTTP checks"
    fi
    
    success "Application health check completed"
}

# Check system resources
check_system_resources() {
    log "Checking system resources..."
    
    # Check disk space
    DISK_USAGE=$(df / | awk 'NR==2{print $4}')
    DISK_USAGE_PERCENT=$(df / | awk 'NR==2{print $5}' | sed 's/%//')
    
    verbose "Available disk space: $(df -h / | awk 'NR==2{print $4}')"
    verbose "Disk usage: ${DISK_USAGE_PERCENT}%"
    
    if [ "$DISK_USAGE" -lt "$MIN_DISK_SPACE" ]; then
        error "Low disk space: $(df -h / | awk 'NR==2{print $4}') available"
    elif [ "$DISK_USAGE_PERCENT" -gt 90 ]; then
        warning "High disk usage: ${DISK_USAGE_PERCENT}%"
    fi
    
    # Check memory usage
    if command -v free > /dev/null 2>&1; then
        MEMORY_INFO=$(free -h)
        MEMORY_USAGE_PERCENT=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
        
        verbose "Memory usage: ${MEMORY_USAGE_PERCENT}%"
        verbose "Memory info:\n$MEMORY_INFO"
        
        if [ "$MEMORY_USAGE_PERCENT" -gt 90 ]; then
            warning "High memory usage: ${MEMORY_USAGE_PERCENT}%"
        fi
    fi
    
    # Check CPU load
    if [ -f "/proc/loadavg" ]; then
        LOAD_AVG=$(cat /proc/loadavg | awk '{print $1}')
        CPU_COUNT=$(nproc)
        LOAD_PERCENT=$(echo "$LOAD_AVG $CPU_COUNT" | awk '{printf "%.0f", $1*100/$2}')
        
        verbose "CPU load average: $LOAD_AVG (${LOAD_PERCENT}% of $CPU_COUNT cores)"
        
        if [ "$LOAD_PERCENT" -gt 80 ]; then
            warning "High CPU load: ${LOAD_PERCENT}%"
        fi
    fi
    
    success "System resources check completed"
}

# Check logs for errors
check_logs() {
    log "Checking application logs..."
    
    # Check for recent errors in application logs
    if docker-compose logs --tail=100 app 2>/dev/null | grep -i "error\|exception\|fatal\|critical" > /dev/null; then
        warning "Recent errors found in application logs"
        
        if [ "$VERBOSE" = "--verbose" ] || [ "$VERBOSE" = "true" ]; then
            echo "Recent errors:"
            docker-compose logs --tail=50 app 2>/dev/null | grep -i "error\|exception\|fatal\|critical" | tail -5
        fi
    else
        verbose "No recent errors in application logs"
    fi
    
    # Check PostgreSQL logs
    if docker-compose logs --tail=100 postgres 2>/dev/null | grep -i "error\|fatal" > /dev/null; then
        warning "Recent errors found in PostgreSQL logs"
    else
        verbose "No recent errors in PostgreSQL logs"
    fi
    
    success "Log analysis completed"
}

# Check SSL certificates (if applicable)
check_ssl_certificates() {
    log "Checking SSL certificates..."
    
    if [ -f "./nginx/ssl/cert.pem" ]; then
        CERT_EXPIRY=$(openssl x509 -in ./nginx/ssl/cert.pem -noout -enddate 2>/dev/null | cut -d= -f2)
        
        if [ -n "$CERT_EXPIRY" ]; then
            EXPIRY_TIMESTAMP=$(date -d "$CERT_EXPIRY" +%s)
            CURRENT_TIMESTAMP=$(date +%s)
            DAYS_UNTIL_EXPIRY=$(( (EXPIRY_TIMESTAMP - CURRENT_TIMESTAMP) / 86400 ))
            
            verbose "SSL certificate expires: $CERT_EXPIRY"
            verbose "Days until expiry: $DAYS_UNTIL_EXPIRY"
            
            if [ "$DAYS_UNTIL_EXPIRY" -lt 30 ]; then
                warning "SSL certificate expires in $DAYS_UNTIL_EXPIRY days"
            elif [ "$DAYS_UNTIL_EXPIRY" -lt 7 ]; then
                error "SSL certificate expires in $DAYS_UNTIL_EXPIRY days"
            fi
        fi
    else
        verbose "SSL certificate not found (development mode?)"
    fi
    
    success "SSL certificate check completed"
}

# Perform security checks
check_security() {
    log "Performing security checks..."
    
    # Check for exposed sensitive files
    SENSITIVE_FILES=(".env" "*.key" "*.pem" "secrets.txt")
    for pattern in "${SENSITIVE_FILES[@]}"; do
        if find . -name "$pattern" -type f 2>/dev/null | grep -v "./scripts" > /dev/null; then
            warning "Sensitive file pattern '$pattern' found in working directory"
        fi
    done
    
    # Check container security
    if docker-compose exec -T app whoami 2>/dev/null | grep -q "root"; then
        warning "Application container is running as root"
    else
        verbose "Application container is running as non-root user"
    fi
    
    # Check for default passwords in environment
    if grep -q "password.*=.*password\|password.*=.*123\|password.*=.*admin" .env 2>/dev/null; then
        error "Default or weak passwords detected in environment"
    fi
    
    success "Security check completed"
}

# Send alerts if configured
send_alerts() {
    if [ -n "$ALERT_WEBHOOK" ] && [ "$OVERALL_STATUS" != "HEALTHY" ]; then
        log "Sending health alert..."
        
        ALERT_PAYLOAD=$(cat << EOF
{
    "status": "$OVERALL_STATUS",
    "timestamp": "$(date -Iseconds)",
    "service": "AI Teddy Bear",
    "failed_checks": $(printf '%s\n' "${FAILED_CHECKS[@]}" | jq -R . | jq -s .),
    "warning_checks": $(printf '%s\n' "${WARNING_CHECKS[@]}" | jq -R . | jq -s .)
}
EOF
)
        
        if command -v curl > /dev/null 2>&1; then
            curl -X POST "$ALERT_WEBHOOK" \
                -H "Content-Type: application/json" \
                -d "$ALERT_PAYLOAD" > /dev/null 2>&1 || warning "Failed to send alert"
        fi
    fi
}

# Generate health report
generate_health_report() {
    mkdir -p "$HEALTH_REPORT_DIR"
    REPORT_FILE="$HEALTH_REPORT_DIR/health-report-$(date +%Y%m%d_%H%M%S).json"
    
    cat > "$REPORT_FILE" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "overall_status": "$OVERALL_STATUS",
    "check_type": "$CHECK_TYPE",
    "system_info": {
        "hostname": "$(hostname)",
        "uptime": "$(uptime -p 2>/dev/null || echo 'Unknown')",
        "load_average": "$(cat /proc/loadavg 2>/dev/null | awk '{print $1, $2, $3}' || echo 'Unknown')"
    },
    "docker_info": {
        "version": "$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'Unknown')",
        "compose_version": "$(docker-compose version --short 2>/dev/null || echo 'Unknown')"
    },
    "services": {
        "app": "$(docker-compose ps app | grep -q 'Up' && echo 'running' || echo 'stopped')",
        "postgres": "$(docker-compose ps postgres | grep -q 'Up' && echo 'running' || echo 'stopped')",
        "redis": "$(docker-compose ps redis | grep -q 'Up' && echo 'running' || echo 'stopped')",
        "nginx": "$(docker-compose ps nginx | grep -q 'Up' && echo 'running' || echo 'stopped')"
    },
    "failed_checks": $(printf '%s\n' "${FAILED_CHECKS[@]}" | jq -R . | jq -s .),
    "warning_checks": $(printf '%s\n' "${WARNING_CHECKS[@]}" | jq -R . | jq -s .)
}
EOF

    log "Health report generated: $REPORT_FILE"
}

# Show usage information
show_usage() {
    cat << EOF
AI Teddy Bear Health Check Script

Usage: $0 [check_type] [--verbose]

Check Types:
  all        - Run all health checks (default)
  quick      - Basic connectivity and service checks
  deep       - Comprehensive health and performance checks
  monitoring - Continuous monitoring mode

Options:
  --verbose  - Show detailed output

Examples:
  $0                     # Run all checks
  $0 quick              # Quick health check
  $0 deep --verbose     # Detailed check with verbose output
  $0 monitoring         # Continuous monitoring
EOF
}

# Continuous monitoring mode
monitoring_mode() {
    log "Starting continuous monitoring mode..."
    log "Press Ctrl+C to stop monitoring"
    
    while true; do
        echo "=============================================="
        echo "Health Check - $(date)"
        echo "=============================================="
        
        quick_check
        
        if [ "$OVERALL_STATUS" != "HEALTHY" ]; then
            send_alerts
        fi
        
        echo "Overall Status: $OVERALL_STATUS"
        echo "Next check in 60 seconds..."
        echo
        
        sleep 60
        
        # Reset status for next iteration
        OVERALL_STATUS="HEALTHY"
        FAILED_CHECKS=()
        WARNING_CHECKS=()
    done
}

# Quick check function
quick_check() {
    check_docker
    check_containers
    check_database
    check_redis
}

# Deep check function
deep_check() {
    quick_check
    check_application
    check_system_resources
    check_logs
    check_ssl_certificates
    check_security
}

# Main health check function
main() {
    # Handle help flag
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        show_usage
        exit 0
    fi
    
    log "Starting health check (type: $CHECK_TYPE)..."
    
    load_environment
    
    case $CHECK_TYPE in
        "quick")
            quick_check
            ;;
        "deep")
            deep_check
            ;;
        "monitoring")
            monitoring_mode
            ;;
        "all"|*)
            deep_check
            ;;
    esac
    
    generate_health_report
    send_alerts
    
    # Final status report
    echo
    echo "=============================================="
    echo "Health Check Summary"
    echo "=============================================="
    echo "Overall Status: $OVERALL_STATUS"
    echo "Failed Checks: ${#FAILED_CHECKS[@]}"
    echo "Warning Checks: ${#WARNING_CHECKS[@]}"
    
    if [ ${#FAILED_CHECKS[@]} -gt 0 ]; then
        echo
        echo "Failed Checks:"
        printf '  - %s\n' "${FAILED_CHECKS[@]}"
    fi
    
    if [ ${#WARNING_CHECKS[@]} -gt 0 ]; then
        echo
        echo "Warning Checks:"
        printf '  - %s\n' "${WARNING_CHECKS[@]}"
    fi
    
    echo "=============================================="
    
    # Exit with appropriate code
    case $OVERALL_STATUS in
        "HEALTHY")
            exit 0
            ;;
        "WARNING")
            exit 1
            ;;
        "CRITICAL")
            exit 2
            ;;
    esac
}

# Error handling for monitoring mode
trap 'log "Health check interrupted"; exit 0' INT TERM

# Run main function
main "$@"
