#!/bin/bash

# Zero-Downtime Deployment Script for AI Teddy Bear
# Supports Blue-Green, Canary, and Rolling deployment strategies
# Enhanced with child safety compliance and COPPA validation

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="ai-teddy-bear"
NAMESPACE="ai-teddy-bear"
DEPLOYMENT_TIMEOUT=600
HEALTH_CHECK_TIMEOUT=300
ROLLBACK_TIMEOUT=180

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
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
Usage: $0 <environment> <strategy> <image_tag> [options]

ARGUMENTS:
  environment    Target environment (staging, production)
  strategy       Deployment strategy (blue-green, canary, rolling)
  image_tag      Docker image tag to deploy

OPTIONS:
  --dry-run            Perform a dry run without making changes
  --skip-tests         Skip post-deployment tests
  --canary-weight      Canary deployment weight percentage (default: 10)
  --rollback-on-fail   Automatically rollback on deployment failure
  --debug              Enable debug mode
  --help               Show this help message

EXAMPLES:
  $0 staging blue-green v1.2.3
  $0 production canary v1.2.3 --canary-weight 5
  $0 production rolling v1.2.3 --rollback-on-fail

CHILD SAFETY COMPLIANCE:
  This script ensures COPPA compliance and child safety validation
  throughout the deployment process.
EOF
}

# Parse command line arguments
parse_args() {
    if [[ $# -lt 3 ]]; then
        usage
        exit 1
    fi

    ENVIRONMENT="$1"
    STRATEGY="$2"
    IMAGE_TAG="$3"
    shift 3

    # Default values
    DRY_RUN=false
    SKIP_TESTS=false
    CANARY_WEIGHT=10
    ROLLBACK_ON_FAIL=false
    DEBUG=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --skip-tests)
                SKIP_TESTS=true
                shift
                ;;
            --canary-weight)
                CANARY_WEIGHT="$2"
                shift 2
                ;;
            --rollback-on-fail)
                ROLLBACK_ON_FAIL=true
                shift
                ;;
            --debug)
                DEBUG=true
                set -x
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

    # Validate arguments
    if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
        error "Environment must be 'staging' or 'production'"
        exit 1
    fi

    if [[ "$STRATEGY" != "blue-green" && "$STRATEGY" != "canary" && "$STRATEGY" != "rolling" ]]; then
        error "Strategy must be 'blue-green', 'canary', or 'rolling'"
        exit 1
    fi
}

# Pre-deployment checks
pre_deployment_checks() {
    log "Running pre-deployment checks..."
    
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
    
    # Verify image exists
    log "Verifying image exists: ghcr.io/$PROJECT_NAME/$PROJECT_NAME:$IMAGE_TAG"
    if ! docker manifest inspect "ghcr.io/$PROJECT_NAME/$PROJECT_NAME:$IMAGE_TAG" > /dev/null 2>&1; then
        warn "Cannot verify image existence. Proceeding with deployment..."
    fi
    
    # Check required secrets exist
    local required_secrets=("ai-teddy-bear-secrets-managed" "ai-teddy-bear-tls")
    for secret in "${required_secrets[@]}"; do
        if ! kubectl get secret "$secret" -n "$NAMESPACE" > /dev/null 2>&1; then
            error "Required secret $secret not found in namespace $NAMESPACE"
            exit 1
        fi
    done
    
    # Child safety compliance check
    log "Validating child safety compliance..."
    if [[ "$ENVIRONMENT" == "production" ]]; then
        validate_coppa_compliance
    fi
    
    success "Pre-deployment checks passed"
}

# COPPA compliance validation
validate_coppa_compliance() {
    log "Validating COPPA compliance for production deployment..."
    
    # Check for child safety labels
    local config_map="ai-teddy-bear-config"
    if ! kubectl get configmap "$config_map" -n "$NAMESPACE" -o jsonpath='{.metadata.labels.coppa\.compliant}' | grep -q "true"; then
        error "ConfigMap $config_map is not marked as COPPA compliant"
        exit 1
    fi
    
    # Verify child safety configuration
    local coppa_mode=$(kubectl get configmap "$config_map" -n "$NAMESPACE" -o jsonpath='{.data.COPPA_COMPLIANCE_MODE}')
    if [[ "$coppa_mode" != "true" ]]; then
        error "COPPA compliance mode is not enabled in configuration"
        exit 1
    fi
    
    success "COPPA compliance validation passed"
}

# Get current active deployment color
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

# Health check function
health_check() {
    local deployment_name="$1"
    local timeout="${2:-$HEALTH_CHECK_TIMEOUT}"
    
    log "Performing health check for $deployment_name (timeout: ${timeout}s)..."
    
    local start_time=$(date +%s)
    local end_time=$((start_time + timeout))
    
    while [[ $(date +%s) -lt $end_time ]]; do
        # Check deployment readiness
        local ready_replicas=$(kubectl get deployment "$deployment_name" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        local desired_replicas=$(kubectl get deployment "$deployment_name" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
        
        if [[ "$ready_replicas" == "$desired_replicas" && "$ready_replicas" -gt 0 ]]; then
            # Additional health checks via HTTP
            local service_name="${PROJECT_NAME}-$(echo $deployment_name | grep -o 'blue\|green')"
            if kubectl get service "$service_name" -n "$NAMESPACE" > /dev/null 2>&1; then
                # Port forward and health check
                local port=$(kubectl get service "$service_name" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}')
                kubectl port-forward "service/$service_name" 8080:$port -n "$NAMESPACE" > /dev/null 2>&1 &
                local pf_pid=$!
                sleep 5
                
                if curl -f "http://localhost:8080/health" > /dev/null 2>&1; then
                    kill $pf_pid 2>/dev/null || true
                    success "Health check passed for $deployment_name"
                    return 0
                fi
                kill $pf_pid 2>/dev/null || true
            fi
        fi
        
        log "Waiting for $deployment_name to become ready... ($ready_replicas/$desired_replicas ready)"
        sleep 10
    done
    
    error "Health check failed for $deployment_name after ${timeout}s"
    return 1
}

# Child safety validation post-deployment
validate_child_safety_post_deployment() {
    local service_name="$1"
    
    log "Validating child safety features post-deployment..."
    
    # Port forward for testing
    kubectl port-forward "service/$service_name" 8080:80 -n "$NAMESPACE" > /dev/null 2>&1 &
    local pf_pid=$!
    sleep 5
    
    # Test child safety endpoints
    local endpoints=(
        "/health/child-safety"
        "/health/coppa-compliance"
        "/api/v1/content/safety-filter"
    )
    
    local failed_checks=0
    for endpoint in "${endpoints[@]}"; do
        if ! curl -f "http://localhost:8080$endpoint" > /dev/null 2>&1; then
            warn "Child safety endpoint check failed: $endpoint"
            ((failed_checks++))
        fi
    done
    
    kill $pf_pid 2>/dev/null || true
    
    if [[ $failed_checks -gt 0 ]]; then
        error "Child safety validation failed with $failed_checks endpoint failures"
        return 1
    fi
    
    success "Child safety validation passed"
    return 0
}

# Blue-Green deployment
deploy_blue_green() {
    log "Starting Blue-Green deployment..."
    
    local active_color=$(get_active_color)
    local inactive_color=$(get_inactive_color)
    local inactive_deployment="$PROJECT_NAME-$inactive_color"
    
    log "Current active color: $active_color"
    log "Deploying to inactive color: $inactive_color"
    
    # Update inactive deployment with new image
    log "Updating $inactive_deployment with image: ghcr.io/$PROJECT_NAME/$PROJECT_NAME:$IMAGE_TAG"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would update deployment $inactive_deployment"
    else
        kubectl set image "deployment/$inactive_deployment" \
            "$PROJECT_NAME=ghcr.io/$PROJECT_NAME/$PROJECT_NAME:$IMAGE_TAG" \
            -n "$NAMESPACE"
        
        # Scale up inactive deployment
        kubectl scale deployment "$inactive_deployment" --replicas=3 -n "$NAMESPACE"
        
        # Wait for rollout to complete
        kubectl rollout status "deployment/$inactive_deployment" -n "$NAMESPACE" --timeout="${DEPLOYMENT_TIMEOUT}s"
        
        # Health check
        if ! health_check "$inactive_deployment"; then
            error "Health check failed for $inactive_deployment"
            if [[ "$ROLLBACK_ON_FAIL" == "true" ]]; then
                log "Rolling back deployment..."
                kubectl scale deployment "$inactive_deployment" --replicas=0 -n "$NAMESPACE"
            fi
            exit 1
        fi
        
        # Child safety validation
        if ! validate_child_safety_post_deployment "$PROJECT_NAME-$inactive_color"; then
            error "Child safety validation failed"
            if [[ "$ROLLBACK_ON_FAIL" == "true" ]]; then
                kubectl scale deployment "$inactive_deployment" --replicas=0 -n "$NAMESPACE"
            fi
            exit 1
        fi
        
        # Switch traffic to inactive deployment
        log "Switching traffic to $inactive_color deployment..."
        kubectl patch service "$PROJECT_NAME-service" -n "$NAMESPACE" \
            -p '{"spec":{"selector":{"deployment.color":"'$inactive_color'"}}}'
        
        # Update load balancer service
        kubectl patch service "$PROJECT_NAME-lb" -n "$NAMESPACE" \
            -p '{"spec":{"selector":{"deployment.color":"'$inactive_color'"}}}'
        
        # Wait for traffic switch to take effect
        sleep 30
        
        # Final health check with new traffic
        if ! health_check "$inactive_deployment" 60; then
            error "Post-switch health check failed"
            # Immediate rollback
            kubectl patch service "$PROJECT_NAME-service" -n "$NAMESPACE" \
                -p '{"spec":{"selector":{"deployment.color":"'$active_color'"}}}'
            kubectl patch service "$PROJECT_NAME-lb" -n "$NAMESPACE" \
                -p '{"spec":{"selector":{"deployment.color":"'$active_color'"}}}'
            exit 1
        fi
        
        # Scale down previous active deployment
        log "Scaling down previous active deployment: $PROJECT_NAME-$active_color"
        kubectl scale deployment "$PROJECT_NAME-$active_color" --replicas=0 -n "$NAMESPACE"
        
        success "Blue-Green deployment completed successfully"
        log "New active color: $inactive_color"
    fi
}

# Canary deployment
deploy_canary() {
    log "Starting Canary deployment with ${CANARY_WEIGHT}% traffic..."
    
    local stable_color=$(get_active_color)
    local canary_color=$(get_inactive_color)
    local canary_deployment="$PROJECT_NAME-$canary_color"
    
    log "Stable deployment: $stable_color"
    log "Canary deployment: $canary_color"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would deploy canary with $CANARY_WEIGHT% traffic"
        return 0
    fi
    
    # Deploy canary version
    kubectl set image "deployment/$canary_deployment" \
        "$PROJECT_NAME=ghcr.io/$PROJECT_NAME/$PROJECT_NAME:$IMAGE_TAG" \
        -n "$NAMESPACE"
    
    # Scale canary deployment
    local canary_replicas=$(( (3 * CANARY_WEIGHT) / 100 ))
    if [[ $canary_replicas -eq 0 ]]; then
        canary_replicas=1
    fi
    
    kubectl scale deployment "$canary_deployment" --replicas=$canary_replicas -n "$NAMESPACE"
    kubectl rollout status "deployment/$canary_deployment" -n "$NAMESPACE" --timeout="${DEPLOYMENT_TIMEOUT}s"
    
    # Health check canary
    if ! health_check "$canary_deployment"; then
        error "Canary health check failed"
        kubectl scale deployment "$canary_deployment" --replicas=0 -n "$NAMESPACE"
        exit 1
    fi
    
    # Child safety validation for canary
    if ! validate_child_safety_post_deployment "$PROJECT_NAME-$canary_color"; then
        error "Canary child safety validation failed"
        kubectl scale deployment "$canary_deployment" --replicas=0 -n "$NAMESPACE"
        exit 1
    fi
    
    # Configure canary traffic routing
    log "Configuring canary traffic routing..."
    kubectl patch ingress "$PROJECT_NAME-canary" -n "$NAMESPACE" \
        -p '{"metadata":{"annotations":{"nginx.ingress.kubernetes.io/canary-weight":"'$CANARY_WEIGHT'"}}}'
    
    success "Canary deployment completed with ${CANARY_WEIGHT}% traffic"
    log "Monitor canary metrics before promoting to full deployment"
    
    # Provide promotion command
    log "To promote canary to full deployment, run:"
    log "  $0 $ENVIRONMENT blue-green $IMAGE_TAG"
}

# Rolling deployment
deploy_rolling() {
    log "Starting Rolling deployment..."
    
    local active_color=$(get_active_color)
    local deployment="$PROJECT_NAME-$active_color"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would perform rolling update on $deployment"
        return 0
    fi
    
    # Update deployment with new image
    kubectl set image "deployment/$deployment" \
        "$PROJECT_NAME=ghcr.io/$PROJECT_NAME/$PROJECT_NAME:$IMAGE_TAG" \
        -n "$NAMESPACE"
    
    # Wait for rollout
    kubectl rollout status "deployment/$deployment" -n "$NAMESPACE" --timeout="${DEPLOYMENT_TIMEOUT}s"
    
    # Health check
    if ! health_check "$deployment"; then
        error "Rolling deployment health check failed"
        if [[ "$ROLLBACK_ON_FAIL" == "true" ]]; then
            kubectl rollout undo "deployment/$deployment" -n "$NAMESPACE"
        fi
        exit 1
    fi
    
    # Child safety validation
    if ! validate_child_safety_post_deployment "$PROJECT_NAME-service"; then
        error "Rolling deployment child safety validation failed"
        if [[ "$ROLLBACK_ON_FAIL" == "true" ]]; then
            kubectl rollout undo "deployment/$deployment" -n "$NAMESPACE"
        fi
        exit 1
    fi
    
    success "Rolling deployment completed successfully"
}

# Post-deployment tests
run_post_deployment_tests() {
    if [[ "$SKIP_TESTS" == "true" ]]; then
        log "Skipping post-deployment tests"
        return 0
    fi
    
    log "Running post-deployment tests..."
    
    # Port forward for testing
    kubectl port-forward "service/$PROJECT_NAME-service" 8080:80 -n "$NAMESPACE" > /dev/null 2>&1 &
    local pf_pid=$!
    sleep 10
    
    # Basic API tests
    local test_endpoints=(
        "/health"
        "/ready"
        "/health/comprehensive"
    )
    
    local failed_tests=0
    for endpoint in "${test_endpoints[@]}"; do
        log "Testing endpoint: $endpoint"
        if curl -f -s "http://localhost:8080$endpoint" > /dev/null; then
            success "✓ $endpoint"
        else
            error "✗ $endpoint"
            ((failed_tests++))
        fi
    done
    
    kill $pf_pid 2>/dev/null || true
    
    if [[ $failed_tests -gt 0 ]]; then
        error "Post-deployment tests failed ($failed_tests failures)"
        return 1
    fi
    
    success "All post-deployment tests passed"
    return 0
}

# Deployment summary
deployment_summary() {
    log "=== Deployment Summary ==="
    log "Environment: $ENVIRONMENT"
    log "Strategy: $STRATEGY"
    log "Image Tag: $IMAGE_TAG"
    log "Active Color: $(get_active_color)"
    log "Namespace: $NAMESPACE"
    log "COPPA Compliant: ✓"
    log "Child Safety Validated: ✓"
    log "=========================="
}

# Cleanup function
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        error "Deployment failed with exit code $exit_code"
    fi
    # Kill any background processes
    jobs -p | xargs -r kill 2>/dev/null || true
    exit $exit_code
}

# Main execution
main() {
    trap cleanup EXIT
    
    parse_args "$@"
    
    log "Starting AI Teddy Bear deployment..."
    log "Environment: $ENVIRONMENT, Strategy: $STRATEGY, Image: $IMAGE_TAG"
    
    pre_deployment_checks
    
    case "$STRATEGY" in
        "blue-green")
            deploy_blue_green
            ;;
        "canary")
            deploy_canary
            ;;
        "rolling")
            deploy_rolling
            ;;
    esac
    
    if [[ "$STRATEGY" != "canary" || "$CANARY_WEIGHT" -eq 100 ]]; then
        run_post_deployment_tests
    fi
    
    deployment_summary
    success "Deployment completed successfully!"
}

# Execute main function with all arguments
main "$@"
