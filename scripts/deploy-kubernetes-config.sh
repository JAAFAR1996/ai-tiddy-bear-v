#!/bin/bash

# Deploy Kubernetes Configuration for AI Teddy Bear
# =================================================
# This script deploys the complete Kubernetes configuration with proper secret handling

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_NAME="deploy-kubernetes-config.sh"
ENVIRONMENT="${ENVIRONMENT:-production}"
NAMESPACE="ai-teddy-bear"
KUBECTL_CMD="${KUBECTL_CMD:-kubectl}"
KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Helper functions
check_dependencies() {
    log_info "Checking dependencies..."
    
    local missing_deps=()
    
    if ! command -v $KUBECTL_CMD &> /dev/null; then
        missing_deps+=("kubectl")
    fi
    
    if ! command -v openssl &> /dev/null; then
        missing_deps+=("openssl")
    fi
    
    if ! command -v base64 &> /dev/null; then
        missing_deps+=("base64")
    fi
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        log_error "Please install the missing dependencies and try again."
        exit 1
    fi
    
    log_success "All dependencies are available"
}

check_kubernetes_connection() {
    log_info "Checking Kubernetes connection..."
    
    if ! $KUBECTL_CMD cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        log_error "Please check your kubeconfig: $KUBECONFIG"
        exit 1
    fi
    
    local cluster_info=$($KUBECTL_CMD cluster-info | head -1)
    log_success "Connected to Kubernetes cluster: $cluster_info"
}

generate_secure_secret() {
    local length=${1:-32}
    openssl rand -base64 $length | tr -d "=+/" | cut -c1-$length
}

generate_jwt_secret() {
    openssl rand -base64 64 | tr -d "=+/" | cut -c1-64
}

create_namespace() {
    log_info "Creating namespace: $NAMESPACE"
    
    if $KUBECTL_CMD get namespace $NAMESPACE &> /dev/null; then
        log_warning "Namespace '$NAMESPACE' already exists"
    else
        $KUBECTL_CMD create namespace $NAMESPACE
        log_success "Namespace '$NAMESPACE' created"
    fi
    
    # Label the namespace
    $KUBECTL_CMD label namespace $NAMESPACE app=ai-teddy-bear environment=$ENVIRONMENT --overwrite
}

create_secrets_from_env() {
    log_info "Creating Kubernetes secrets from environment variables..."
    
    # Create temporary secret file
    local temp_secret_file=$(mktemp)
    
    # Generate secrets if not provided
    local database_password="${DATABASE_PASSWORD:-$(generate_secure_secret 32)}"
    local redis_password="${REDIS_PASSWORD:-$(generate_secure_secret 32)}"
    local jwt_secret="${JWT_SECRET_KEY:-$(generate_jwt_secret)}"
    
    # Build database URL
    local database_url="postgresql://ai_teddy_user:${database_password}@postgres-service:5432/ai_teddy_bear_${ENVIRONMENT}"
    local redis_url="redis://:${redis_password}@redis-service:6379/0"
    
    cat > "$temp_secret_file" << EOF
apiVersion: v1
kind: Secret
metadata:
  name: ai-teddy-bear-secrets
  namespace: $NAMESPACE
  labels:
    app: ai-teddy-bear
    component: secrets
    environment: $ENVIRONMENT
type: Opaque
stringData:
  # Database Configuration
  DATABASE_URL: "$database_url"
  
  # Redis Configuration
  REDIS_URL: "$redis_url"
  
  # JWT Secret
  JWT_SECRET_KEY: "$jwt_secret"
  
  # AI Provider Keys
  OPENAI_API_KEY: "${OPENAI_API_KEY:-sk-placeholder-key-replace-with-real}"
  ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY:-placeholder-key-replace-with-real}"
  
  # AWS Credentials
  AWS_ACCESS_KEY_ID: "${AWS_ACCESS_KEY_ID:-placeholder-access-key}"
  AWS_SECRET_ACCESS_KEY: "${AWS_SECRET_ACCESS_KEY:-placeholder-secret-key}"
  
  # Communication Service Keys
  SENDGRID_API_KEY: "${SENDGRID_API_KEY:-SG.placeholder-key}"
  FIREBASE_SERVICE_ACCOUNT: '${FIREBASE_SERVICE_ACCOUNT:-"{\"type\":\"service_account\",\"project_id\":\"placeholder\"}"}'
  
  # External Service Keys
  STRIPE_API_KEY: "${STRIPE_API_KEY:-sk_test_placeholder}"
  STRIPE_WEBHOOK_SECRET: "${STRIPE_WEBHOOK_SECRET:-whsec_placeholder}"
EOF
    
    # Apply the secret
    $KUBECTL_CMD apply -f "$temp_secret_file"
    
    # Clean up
    rm "$temp_secret_file"
    
    # Save generated secrets for reference
    local secrets_backup_file="kubernetes/secrets-backup-$(date +%Y%m%d_%H%M%S).env"
    mkdir -p kubernetes
    
    cat > "$secrets_backup_file" << EOF
# Generated Kubernetes Secrets - $(date)
# IMPORTANT: Keep this file secure and back it up safely

DATABASE_PASSWORD=$database_password
REDIS_PASSWORD=$redis_password
JWT_SECRET_KEY=$jwt_secret

# Database and Redis URLs
DATABASE_URL=$database_url
REDIS_URL=$redis_url
EOF
    
    chmod 600 "$secrets_backup_file"
    
    log_success "Secrets created successfully"
    log_info "Generated secrets backup: $secrets_backup_file"
}

deploy_configuration() {
    log_info "Deploying Kubernetes configuration..."
    
    # Apply the main configuration
    if [[ -f "kubernetes/config-management.yaml" ]]; then
        $KUBECTL_CMD apply -f kubernetes/config-management.yaml
        log_success "Configuration deployed"
    else
        log_error "Configuration file not found: kubernetes/config-management.yaml"
        exit 1
    fi
}

wait_for_deployment() {
    log_info "Waiting for deployment to be ready..."
    
    local deployment_name="ai-teddy-bear-app"
    local timeout=300  # 5 minutes
    
    if $KUBECTL_CMD wait --for=condition=available --timeout=${timeout}s deployment/$deployment_name -n $NAMESPACE; then
        log_success "Deployment is ready"
    else
        log_error "Deployment did not become ready within $timeout seconds"
        
        # Show some debug information
        log_info "Deployment status:"
        $KUBECTL_CMD get deployment $deployment_name -n $NAMESPACE -o wide
        
        log_info "Pod status:"
        $KUBECTL_CMD get pods -n $NAMESPACE -l app=ai-teddy-bear
        
        log_info "Recent events:"
        $KUBECTL_CMD get events -n $NAMESPACE --sort-by='.lastTimestamp' | tail -10
        
        exit 1
    fi
}

verify_deployment() {
    log_info "Verifying deployment..."
    
    # Check pods
    local pod_count=$($KUBECTL_CMD get pods -n $NAMESPACE -l app=ai-teddy-bear --no-headers | wc -l)
    local ready_pods=$($KUBECTL_CMD get pods -n $NAMESPACE -l app=ai-teddy-bear -o jsonpath='{range .items[*]}{.status.conditions[?(@.type=="Ready")].status}{" "}{end}' | grep -o True | wc -l)
    
    log_info "Pods status: $ready_pods/$pod_count ready"
    
    if [[ $ready_pods -eq 0 ]]; then
        log_error "No pods are ready"
        return 1
    fi
    
    # Check service
    local service_endpoints=$($KUBECTL_CMD get endpoints ai-teddy-bear-service -n $NAMESPACE -o jsonpath='{.subsets[*].addresses}' | wc -w)
    log_info "Service endpoints: $service_endpoints"
    
    # Test health endpoint if possible
    if command -v kubectl-port-forward &> /dev/null || $KUBECTL_CMD version --client -o json | grep -q '"clientVersion"'; then
        log_info "Testing health endpoint..."
        
        # Start port forwarding in background
        $KUBECTL_CMD port-forward -n $NAMESPACE service/ai-teddy-bear-service 8080:80 &
        local port_forward_pid=$!
        
        # Wait a moment for port forwarding to establish
        sleep 5
        
        # Test the health endpoint
        if curl -f http://localhost:8080/health > /dev/null 2>&1; then
            log_success "Health endpoint is responding"
        else
            log_warning "Health endpoint is not responding (this may be normal during startup)"
        fi
        
        # Clean up port forwarding
        kill $port_forward_pid 2>/dev/null || true
    fi
    
    log_success "Deployment verification completed"
}

show_deployment_info() {
    log_info "Deployment Information:"
    
    echo "Namespace: $NAMESPACE"
    echo "Deployment: ai-teddy-bear-app"
    echo "Service: ai-teddy-bear-service"
    echo ""
    
    # Show pod information
    echo "Pods:"
    $KUBECTL_CMD get pods -n $NAMESPACE -l app=ai-teddy-bear -o wide
    echo ""
    
    # Show service information
    echo "Services:"
    $KUBECTL_CMD get services -n $NAMESPACE -o wide
    echo ""
    
    # Show ingress information
    if $KUBECTL_CMD get ingress -n $NAMESPACE &> /dev/null; then
        echo "Ingress:"
        $KUBECTL_CMD get ingress -n $NAMESPACE -o wide
        echo ""
    fi
    
    # Show configuration information
    echo "ConfigMaps:"
    $KUBECTL_CMD get configmaps -n $NAMESPACE -l app=ai-teddy-bear
    echo ""
    
    echo "Secrets:"
    $KUBECTL_CMD get secrets -n $NAMESPACE -l app=ai-teddy-bear
    echo ""
    
    # Show resource usage if metrics server is available
    if $KUBECTL_CMD top pods -n $NAMESPACE &> /dev/null; then
        echo "Resource Usage:"
        $KUBECTL_CMD top pods -n $NAMESPACE -l app=ai-teddy-bear
        echo ""
    fi
}

show_next_steps() {
    log_info "Next Steps:"
    echo ""
    echo "1. Verify the deployment:"
    echo "   $KUBECTL_CMD get all -n $NAMESPACE"
    echo ""
    echo "2. Check application logs:"
    echo "   $KUBECTL_CMD logs -n $NAMESPACE -l app=ai-teddy-bear -f"
    echo ""
    echo "3. Test the application:"
    echo "   $KUBECTL_CMD port-forward -n $NAMESPACE service/ai-teddy-bear-service 8080:80"
    echo "   curl http://localhost:8080/health"
    echo ""
    echo "4. Access configuration API:"
    echo "   curl http://localhost:8080/api/config/health"
    echo ""
    echo "5. Update secrets if needed:"
    echo "   $KUBECTL_CMD edit secret ai-teddy-bear-secrets -n $NAMESPACE"
    echo ""
    echo "6. Scale the deployment:"
    echo "   $KUBECTL_CMD scale deployment ai-teddy-bear-app --replicas=5 -n $NAMESPACE"
    echo ""
    echo "7. Configure ingress (if external access needed):"
    echo "   $KUBECTL_CMD get ingress -n $NAMESPACE"
    echo ""
}

cleanup_on_error() {
    log_error "Deployment failed. Cleaning up..."
    
    # Optionally remove the namespace (commented out for safety)
    # $KUBECTL_CMD delete namespace $NAMESPACE
    
    log_info "Manual cleanup may be required"
    log_info "To remove everything: $KUBECTL_CMD delete namespace $NAMESPACE"
}

# Main execution
main() {
    log_info "Starting Kubernetes deployment for AI Teddy Bear ($ENVIRONMENT environment)"
    
    # Set up error handling
    trap cleanup_on_error ERR
    
    # Preliminary checks
    check_dependencies
    check_kubernetes_connection
    
    # Create namespace
    create_namespace
    
    # Create secrets
    create_secrets_from_env
    
    # Deploy configuration
    deploy_configuration
    
    # Wait for and verify deployment
    wait_for_deployment
    verify_deployment
    
    # Show information
    show_deployment_info
    show_next_steps
    
    log_success "Kubernetes deployment completed successfully!"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment|-e)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --namespace|-n)
            NAMESPACE="$2"
            shift 2
            ;;
        --kubectl)
            KUBECTL_CMD="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -e, --environment ENV    Set environment (default: production)"
            echo "  -n, --namespace NS       Set namespace (default: ai-teddy-bear)"
            echo "      --kubectl CMD        Set kubectl command (default: kubectl)"
            echo "  -h, --help              Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  OPENAI_API_KEY          OpenAI API key"
            echo "  ANTHROPIC_API_KEY       Anthropic API key"
            echo "  AWS_ACCESS_KEY_ID       AWS access key"
            echo "  AWS_SECRET_ACCESS_KEY   AWS secret key"
            echo "  SENDGRID_API_KEY        SendGrid API key"
            echo "  STRIPE_API_KEY          Stripe API key"
            echo "  ... and more (see script for full list)"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi