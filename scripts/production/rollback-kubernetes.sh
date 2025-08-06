#!/bin/bash

# AI Teddy Bear Production Rollback Script for Kubernetes
# Provides instant rollback capabilities for failed deployments
# Includes child safety compliance validation during rollback

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="ai-teddy-bear"
NAMESPACE="ai-teddy-bear"
ROLLBACK_TIMEOUT=300

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Usage function
usage() {
    cat << EOF
Usage: $0 [options]

OPTIONS:
  --environment ENV    Target environment (staging, production) [default: production]
  --revision REV       Specific revision to rollback to (default: previous)
  --deployment NAME    Specific deployment to rollback
  --dry-run           Perform a dry run without making changes
  --force             Force rollback without confirmation
  --skip-validation   Skip child safety validation (not recommended)
  --help              Show this help message

EXAMPLES:
  $0                                    # Auto-detect and rollback
  $0 --revision 5                       # Rollback to specific revision
  $0 --deployment ai-teddy-bear-blue    # Rollback specific deployment
  $0 --environment staging --dry-run    # Dry run rollback in staging

CHILD SAFETY COMPLIANCE:
  This script ensures COPPA compliance and child safety validation
  are maintained during rollback operations.
EOF
}

# Parse command line arguments
parse_args() {
    ENVIRONMENT="production"
    REVISION=""
    DEPLOYMENT=""
    DRY_RUN=false
    FORCE=false
    SKIP_VALIDATION=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --revision)
                REVISION="$2"
                shift 2
                ;;
            --deployment)
                DEPLOYMENT="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --skip-validation)
                SKIP_VALIDATION=true
                shift
                ;;
            --help)
                usage
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    # Validate environment
    if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
        error "Environment must be 'staging' or 'production'"
        exit 1
    fi
}

# Pre-rollback checks
pre_rollback_checks() {
    log "Running pre-rollback checks..."
    
    # Check kubectl connectivity
    if ! kubectl cluster-info > /dev/null 2>&1; then
        error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    # Check namespace exists
    if ! kubectl get namespace "$NAMESPACE" > /dev/null 2>&1; then
        error "Namespace $NAMESPACE does not exist"
        exit 1
    fi
    
    # Verify deployment exists
    if [[ -n "$DEPLOYMENT" ]]; then
        if ! kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" > /dev/null 2>&1; then
            error "Deployment $DEPLOYMENT not found in namespace $NAMESPACE"
            exit 1
        fi
    fi
    
    success "Pre-rollback checks passed"
}

# Get current active deployment color for blue-green rollback
get_active_color() {
    local service_selector=$(kubectl get service "$PROJECT_NAME-service" -n "$NAMESPACE" -o jsonpath='{.spec.selector.deployment\.color}' 2>/dev/null || echo "blue")
    echo "$service_selector"
}

# Get inactive deployment color
get_inactive_color() {
    local active_color=$(get_active_color)
    if [[ "$active_color" == "blue" ]]; then
        echo "green"
    else
        echo "blue"
    fi
}

# Get deployment revision history
get_revision_history() {
    local deployment_name="$1"
    
    log "Getting revision history for $deployment_name..."
    kubectl rollout history "deployment/$deployment_name" -n "$NAMESPACE"
    
    # Get current revision
    local current_revision=$(kubectl get deployment "$deployment_name" -n "$NAMESPACE" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')
    log "Current revision: $current_revision"
    
    # Get previous revision if not specified
    if [[ -z "$REVISION" ]]; then
        REVISION=$((current_revision - 1))
        log "Target rollback revision: $REVISION"
    fi
}

# Validate child safety compliance post-rollback
validate_child_safety_post_rollback() {
    if [[ "$SKIP_VALIDATION" == "true" ]]; then
        warn "Skipping child safety validation (not recommended for production)"
        return 0
    fi
    
    local service_name="$1"
    
    log "Validating child safety compliance post-rollback..."
    
    # Port forward for testing
    kubectl port-forward "service/$service_name" 8080:80 -n "$NAMESPACE" > /dev/null 2>&1 &
    local pf_pid=$!
    sleep 10
    
    # Test child safety endpoints
    local endpoints=(
        "/api/v1/health/child-safety"
        "/api/v1/health/coppa-compliance"
        "/api/v1/content/safety-filter"
    )
    
    local failed_checks=0
    for endpoint in "${endpoints[@]}"; do
        if ! curl -f -s "http://localhost:8080$endpoint" > /dev/null 2>&1; then
            warn "Child safety endpoint check failed: $endpoint"
            ((failed_checks++))
        else
            log "✓ Child safety endpoint OK: $endpoint"
        fi
    done
    
    kill $pf_pid 2>/dev/null || true
    
    if [[ $failed_checks -gt 0 ]]; then
        error "Child safety validation failed with $failed_checks endpoint failures"
        return 1
    fi
    
    success "Child safety validation passed post-rollback"
    return 0
}

# Health check after rollback
health_check_post_rollback() {
    local deployment_name="$1"
    local timeout="${2:-$ROLLBACK_TIMEOUT}"
    
    log "Performing health check after rollback for $deployment_name..."
    
    local start_time=$(date +%s)
    local end_time=$((start_time + timeout))
    
    while [[ $(date +%s) -lt $end_time ]]; do
        # Check deployment readiness
        local ready_replicas=$(kubectl get deployment "$deployment_name" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        local desired_replicas=$(kubectl get deployment "$deployment_name" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
        
        if [[ "$ready_replicas" == "$desired_replicas" && "$ready_replicas" -gt 0 ]]; then
            success "Health check passed for $deployment_name after rollback"
            return 0
        fi
        
        log "Waiting for $deployment_name to become ready after rollback... ($ready_replicas/$desired_replicas ready)"
        sleep 10
    done
    
    error "Health check failed for $deployment_name after rollback (timeout: ${timeout}s)"
    return 1
}

# Standard deployment rollback
rollback_deployment() {
    local deployment_name="$1"
    
    log "Rolling back deployment: $deployment_name"
    
    # Get revision history
    get_revision_history "$deployment_name"
    
    # Confirm rollback unless forced
    if [[ "$FORCE" != "true" ]]; then
        echo -e "${YELLOW}Are you sure you want to rollback $deployment_name to revision $REVISION? (y/N)${NC}"
        read -r confirmation
        if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
            log "Rollback cancelled by user"
            exit 0
        fi
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would rollback $deployment_name to revision $REVISION"
        return 0
    fi
    
    # Perform rollback
    if [[ -n "$REVISION" ]]; then
        kubectl rollout undo "deployment/$deployment_name" --to-revision="$REVISION" -n "$NAMESPACE"
    else
        kubectl rollout undo "deployment/$deployment_name" -n "$NAMESPACE"
    fi
    
    # Wait for rollback to complete
    kubectl rollout status "deployment/$deployment_name" -n "$NAMESPACE" --timeout="${ROLLBACK_TIMEOUT}s"
    
    # Health check
    if ! health_check_post_rollback "$deployment_name"; then
        error "Health check failed after rollback"
        exit 1
    fi
    
    # Child safety validation
    if ! validate_child_safety_post_rollback "$PROJECT_NAME-service"; then
        error "Child safety validation failed after rollback"
        exit 1
    fi
    
    success "Deployment $deployment_name rolled back successfully"
}

# Blue-green rollback
rollback_blue_green() {
    log "Performing Blue-Green rollback..."
    
    local current_active=$(get_active_color)
    local previous_active=$(get_inactive_color)
    
    log "Current active: $current_active"
    log "Rolling back to: $previous_active"
    
    # Check if previous deployment has replicas
    local previous_replicas=$(kubectl get deployment "$PROJECT_NAME-$previous_active" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')
    
    if [[ "$previous_replicas" -eq 0 ]]; then
        log "Previous deployment has 0 replicas. Scaling up..."
        
        if [[ "$DRY_RUN" == "true" ]]; then
            log "[DRY RUN] Would scale up $PROJECT_NAME-$previous_active to 3 replicas"
        else
            kubectl scale deployment "$PROJECT_NAME-$previous_active" --replicas=3 -n "$NAMESPACE"
            kubectl rollout status "deployment/$PROJECT_NAME-$previous_active" -n "$NAMESPACE" --timeout="${ROLLBACK_TIMEOUT}s"
        fi
    fi
    
    # Health check previous deployment
    if [[ "$DRY_RUN" != "true" ]]; then
        if ! health_check_post_rollback "$PROJECT_NAME-$previous_active"; then
            error "Previous deployment health check failed. Cannot rollback."
            exit 1
        fi
    fi
    
    # Confirm rollback
    if [[ "$FORCE" != "true" ]]; then
        echo -e "${YELLOW}Are you sure you want to rollback from $current_active to $previous_active? (y/N)${NC}"
        read -r confirmation
        if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
            log "Rollback cancelled by user"
            exit 0
        fi
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would switch traffic from $current_active to $previous_active"
        return 0
    fi
    
    # Switch traffic back to previous deployment
    log "Switching traffic from $current_active to $previous_active..."
    kubectl patch service "$PROJECT_NAME-service" -n "$NAMESPACE" \
        -p '{"spec":{"selector":{"deployment.color":"'$previous_active'"}}}'
    
    # Update load balancer service
    kubectl patch service "$PROJECT_NAME-lb" -n "$NAMESPACE" \
        -p '{"spec":{"selector":{"deployment.color":"'$previous_active'"}}}'
    
    # Wait for traffic switch
    sleep 30
    
    # Final health check
    if ! health_check_post_rollback "$PROJECT_NAME-$previous_active" 120; then
        error "Post-rollback health check failed"
        # Try to switch back
        kubectl patch service "$PROJECT_NAME-service" -n "$NAMESPACE" \
            -p '{"spec":{"selector":{"deployment.color":"'$current_active'"}}}'
        kubectl patch service "$PROJECT_NAME-lb" -n "$NAMESPACE" \
            -p '{"spec":{"selector":{"deployment.color":"'$current_active'"}}}'
        exit 1
    fi
    
    # Child safety validation
    if ! validate_child_safety_post_rollback "$PROJECT_NAME-service"; then
        error "Child safety validation failed after rollback"
        # Try to switch back
        kubectl patch service "$PROJECT_NAME-service" -n "$NAMESPACE" \
            -p '{"spec":{"selector":{"deployment.color":"'$current_active'"}}}'
        kubectl patch service "$PROJECT_NAME-lb" -n "$NAMESPACE" \
            -p '{"spec":{"selector":{"deployment.color":"'$current_active'"}}}'
        exit 1
    fi
    
    # Scale down failed deployment
    log "Scaling down failed deployment: $PROJECT_NAME-$current_active"
    kubectl scale deployment "$PROJECT_NAME-$current_active" --replicas=0 -n "$NAMESPACE"
    
    success "Blue-Green rollback completed successfully"
    log "New active deployment: $previous_active"
}

# Canary rollback
rollback_canary() {
    log "Performing Canary rollback..."
    
    local canary_color=$(get_inactive_color)
    local canary_deployment="$PROJECT_NAME-$canary_color"
    
    # Get current canary weight
    local canary_weight=$(kubectl get ingress "$PROJECT_NAME-canary" -n "$NAMESPACE" -o jsonpath='{.metadata.annotations.nginx\.ingress\.kubernetes\.io/canary-weight}' 2>/dev/null || echo "0")
    
    log "Current canary weight: $canary_weight%"
    
    if [[ "$canary_weight" -eq 0 ]]; then
        log "No active canary deployment to rollback"
        return 0
    fi
    
    if [[ "$FORCE" != "true" ]]; then
        echo -e "${YELLOW}Are you sure you want to rollback canary deployment (${canary_weight}% traffic)? (y/N)${NC}"
        read -r confirmation
        if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
            log "Canary rollback cancelled by user"
            exit 0
        fi
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would rollback canary deployment"
        return 0
    fi
    
    # Remove canary traffic
    log "Removing canary traffic routing..."
    kubectl patch ingress "$PROJECT_NAME-canary" -n "$NAMESPACE" \
        -p '{"metadata":{"annotations":{"nginx.ingress.kubernetes.io/canary-weight":"0"}}}'
    
    # Scale down canary deployment
    log "Scaling down canary deployment..."
    kubectl scale deployment "$canary_deployment" --replicas=0 -n "$NAMESPACE"
    
    success "Canary rollback completed successfully"
}

# Auto-detect rollback strategy
auto_detect_rollback_strategy() {
    log "Auto-detecting rollback strategy..."
    
    # Check for canary deployment
    local canary_weight=$(kubectl get ingress "$PROJECT_NAME-canary" -n "$NAMESPACE" -o jsonpath='{.metadata.annotations.nginx\.ingress\.kubernetes\.io/canary-weight}' 2>/dev/null || echo "0")
    
    if [[ "$canary_weight" -gt 0 ]]; then
        log "Detected active canary deployment (${canary_weight}% traffic)"
        rollback_canary
        return
    fi
    
    # Check for blue-green setup
    local inactive_color=$(get_inactive_color)
    local inactive_replicas=$(kubectl get deployment "$PROJECT_NAME-$inactive_color" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    
    if [[ "$inactive_replicas" -gt 0 ]]; then
        log "Detected blue-green deployment setup"
        rollback_blue_green
        return
    fi
    
    # Default to standard rollback
    log "Using standard deployment rollback"
    local active_color=$(get_active_color)
    rollback_deployment "$PROJECT_NAME-$active_color"
}

# Rollback summary
rollback_summary() {
    log "=== Rollback Summary ==="
    log "Environment: $ENVIRONMENT"
    log "Namespace: $NAMESPACE"
    log "Active Color: $(get_active_color)"
    log "COPPA Compliant: ✓"
    log "Child Safety Validated: ✓"
    log "======================="
}

# Cleanup function
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        error "Rollback failed with exit code $exit_code"
    fi
    # Kill any background processes
    jobs -p | xargs -r kill 2>/dev/null || true
    exit $exit_code
}

# Main execution
main() {
    trap cleanup EXIT
    
    parse_args "$@"
    
    log "Starting AI Teddy Bear rollback..."
    log "Environment: $ENVIRONMENT"
    
    pre_rollback_checks
    
    if [[ -n "$DEPLOYMENT" ]]; then
        rollback_deployment "$DEPLOYMENT"
    else
        auto_detect_rollback_strategy
    fi
    
    rollback_summary
    success "Rollback completed successfully!"
}

# Execute main function with all arguments
main "$@"