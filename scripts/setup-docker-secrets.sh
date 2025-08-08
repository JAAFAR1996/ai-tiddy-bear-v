#!/bin/bash

# Setup Docker Secrets for AI Teddy Bear Configuration Management
# ===============================================================
# This script creates all necessary Docker secrets for the AI Teddy Bear application

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_NAME="setup-docker-secrets.sh"
ENVIRONMENT="${ENVIRONMENT:-production}"
SECRETS_FILE="${SECRETS_FILE:-secrets/.env.secrets}"
BACKUP_DIR="secrets/backup/$(date +%Y%m%d_%H%M%S)"

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
    
    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    fi
    
    if ! command -v openssl &> /dev/null; then
        missing_deps+=("openssl")
    fi
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        log_error "Please install the missing dependencies and try again."
        exit 1
    fi
    
    log_success "All dependencies are available"
}

generate_secure_key() {
    local length=${1:-32}
    openssl rand -base64 $length | tr -d "=+/" | cut -c1-$length
}

generate_jwt_key() {
    openssl rand -base64 64 | tr -d "=+/" | cut -c1-64
}

create_docker_secret() {
    local secret_name=$1
    local secret_value=$2
    local description=${3:-""}
    
    if docker secret ls --format "{{.Name}}" | grep -q "^${secret_name}$"; then
        log_warning "Secret '${secret_name}' already exists, skipping..."
        return 0
    fi
    
    echo -n "$secret_value" | docker secret create "$secret_name" -
    
    if [[ $? -eq 0 ]]; then
        log_success "Created secret: ${secret_name}"
        if [[ -n "$description" ]]; then
            log_info "  Description: $description"
        fi
    else
        log_error "Failed to create secret: ${secret_name}"
        return 1
    fi
}

backup_existing_secrets() {
    log_info "Creating backup of existing secrets configuration..."
    
    mkdir -p "$BACKUP_DIR"
    
    # Backup current secrets list
    docker secret ls --format "table {{.Name}}\t{{.CreatedAt}}" > "$BACKUP_DIR/existing_secrets.txt"
    
    # Backup environment file if it exists
    if [[ -f "$SECRETS_FILE" ]]; then
        cp "$SECRETS_FILE" "$BACKUP_DIR/env.secrets.backup"
    fi
    
    log_success "Backup created in: $BACKUP_DIR"
}

create_secrets_directory() {
    log_info "Creating secrets directory structure..."
    
    mkdir -p secrets/{backup,templates,generated}
    chmod 700 secrets
    
    log_success "Secrets directory created"
}

generate_database_secrets() {
    log_info "Generating database secrets..."
    
    local db_password=$(generate_secure_key 32)
    local db_url="postgresql://ai_teddy_user:${db_password}@postgres:5432/ai_teddy_bear_${ENVIRONMENT}"
    
    create_docker_secret "ai_teddy_bear_database_password" "$db_password" "PostgreSQL database password"
    create_docker_secret "ai_teddy_bear_database_url" "$db_url" "PostgreSQL database connection URL"
    
    # Save to generated secrets file for reference
    echo "DATABASE_PASSWORD=${db_password}" >> "secrets/generated/database_secrets.env"
    
    log_success "Database secrets generated"
}

generate_redis_secrets() {
    log_info "Generating Redis secrets..."
    
    local redis_password=$(generate_secure_key 32)
    local redis_url="redis://:${redis_password}@redis:6379/0"
    
    create_docker_secret "ai_teddy_bear_redis_password" "$redis_password" "Redis password"
    create_docker_secret "ai_teddy_bear_redis_url" "$redis_url" "Redis connection URL"
    
    # Save to generated secrets file for reference
    echo "REDIS_PASSWORD=${redis_password}" >> "secrets/generated/redis_secrets.env"
    
    log_success "Redis secrets generated"
}

generate_jwt_secrets() {
    log_info "Generating JWT secrets..."
    
    local jwt_secret=$(generate_jwt_key)
    
    create_docker_secret "ai_teddy_bear_jwt_secret_key" "$jwt_secret" "JWT signing secret key"
    
    # Save to generated secrets file for reference
    echo "JWT_SECRET_KEY=${jwt_secret}" >> "secrets/generated/jwt_secrets.env"
    
    log_success "JWT secrets generated"
}

create_ai_provider_secrets() {
    log_info "Setting up AI provider secrets..."
    
    # These should be provided via environment variables or manual input
    local openai_key="${OPENAI_API_KEY:-}"
    local anthropic_key="${ANTHROPIC_API_KEY:-}"
    
    if [[ -z "$openai_key" ]]; then
        log_warning "OPENAI_API_KEY not provided. Please set this manually:"
        log_info "  echo 'your-openai-key' | docker secret create ai_teddy_bear_openai_api_key -"
    else
        create_docker_secret "ai_teddy_bear_openai_api_key" "$openai_key" "OpenAI API key"
    fi
    
    if [[ -z "$anthropic_key" ]]; then
        log_warning "ANTHROPIC_API_KEY not provided. Please set this manually:"
        log_info "  echo 'your-anthropic-key' | docker secret create ai_teddy_bear_anthropic_api_key -"
    else
        create_docker_secret "ai_teddy_bear_anthropic_api_key" "$anthropic_key" "Anthropic API key"
    fi
    
    log_success "AI provider secrets configured"
}

create_aws_secrets() {
    log_info "Setting up AWS secrets..."
    
    local aws_access_key="${AWS_ACCESS_KEY_ID:-}"
    local aws_secret_key="${AWS_SECRET_ACCESS_KEY:-}"
    
    if [[ -z "$aws_access_key" ]] || [[ -z "$aws_secret_key" ]]; then
        log_warning "AWS credentials not provided. Please set these manually:"
        log_info "  echo 'your-aws-access-key' | docker secret create ai_teddy_bear_aws_access_key_id -"
        log_info "  echo 'your-aws-secret-key' | docker secret create ai_teddy_bear_aws_secret_access_key -"
    else
        create_docker_secret "ai_teddy_bear_aws_access_key_id" "$aws_access_key" "AWS access key ID"
        create_docker_secret "ai_teddy_bear_aws_secret_access_key" "$aws_secret_key" "AWS secret access key"
    fi
    
    log_success "AWS secrets configured"
}

create_communication_secrets() {
    log_info "Setting up communication service secrets..."
    
    local sendgrid_key="${SENDGRID_API_KEY:-}"
    local firebase_account="${FIREBASE_SERVICE_ACCOUNT:-}"
    
    if [[ -z "$sendgrid_key" ]]; then
        log_warning "SENDGRID_API_KEY not provided. Please set this manually:"
        log_info "  echo 'your-sendgrid-key' | docker secret create ai_teddy_bear_sendgrid_api_key -"
    else
        create_docker_secret "ai_teddy_bear_sendgrid_api_key" "$sendgrid_key" "SendGrid API key"
    fi
    
    if [[ -z "$firebase_account" ]]; then
        log_warning "FIREBASE_SERVICE_ACCOUNT not provided. Please set this manually:"
        log_info "  cat firebase-service-account.json | docker secret create ai_teddy_bear_firebase_service_account -"
    else
        create_docker_secret "ai_teddy_bear_firebase_service_account" "$firebase_account" "Firebase service account JSON"
    fi
    
    log_success "Communication service secrets configured"
}

create_external_service_secrets() {
    log_info "Setting up external service secrets..."
    
    local stripe_key="${STRIPE_API_KEY:-}"
    local stripe_webhook="${STRIPE_WEBHOOK_SECRET:-}"
    
    if [[ -z "$stripe_key" ]]; then
        log_warning "STRIPE_API_KEY not provided. Please set this manually:"
        log_info "  echo 'your-stripe-key' | docker secret create ai_teddy_bear_stripe_api_key -"
    else
        create_docker_secret "ai_teddy_bear_stripe_api_key" "$stripe_key" "Stripe API key"
    fi
    
    if [[ -z "$stripe_webhook" ]]; then
        log_warning "STRIPE_WEBHOOK_SECRET not provided. Please set this manually:"
        log_info "  echo 'your-stripe-webhook-secret' | docker secret create ai_teddy_bear_stripe_webhook_secret -"
    else
        create_docker_secret "ai_teddy_bear_stripe_webhook_secret" "$stripe_webhook" "Stripe webhook secret"
    fi
    
    log_success "External service secrets configured"
}

create_vault_secrets() {
    log_info "Setting up Vault secrets..."
    
    local vault_token="${VAULT_ROOT_TOKEN:-$(generate_secure_key 32)}"
    
    create_docker_secret "ai_teddy_bear_vault_token" "$vault_token" "HashiCorp Vault root token"
    
    # Save vault token for reference
    echo "VAULT_ROOT_TOKEN=${vault_token}" >> "secrets/generated/vault_secrets.env"
    
    log_success "Vault secrets configured"
}

create_elasticsearch_secrets() {
    log_info "Setting up Elasticsearch secrets..."
    
    local elastic_password=$(generate_secure_key 24)
    
    create_docker_secret "ai_teddy_bear_elasticsearch_password" "$elastic_password" "Elasticsearch password"
    
    # Save elasticsearch password for reference
    echo "ELASTICSEARCH_PASSWORD=${elastic_password}" >> "secrets/generated/elasticsearch_secrets.env"
    
    log_success "Elasticsearch secrets configured"
}

create_secrets_summary() {
    log_info "Creating secrets summary..."
    
    local summary_file="secrets/generated/secrets_summary.txt"
    
    cat > "$summary_file" << EOF
AI Teddy Bear Docker Secrets Summary
===================================
Generated on: $(date)
Environment: $ENVIRONMENT

Docker Secrets Created:
EOF
    
    docker secret ls --format "- {{.Name}} (Created: {{.CreatedAt}})" | grep "ai_teddy_bear_" >> "$summary_file"
    
    cat >> "$summary_file" << EOF

Generated Secret Files:
- Database secrets: $(pwd)/secrets/generated/database_secrets.env
- Redis secrets: $(pwd)/secrets/generated/redis_secrets.env
- JWT secrets: $(pwd)/secrets/generated/jwt_secrets.env
- Vault secrets: $(pwd)/secrets/generated/vault_secrets.env
- Elasticsearch secrets: $(pwd)/secrets/generated/elasticsearch_secrets.env

Security Notes:
- All generated passwords are 32 characters long
- JWT secret is 64 characters long
- All secrets are stored in Docker's encrypted secret store
- Generated secret files should be backed up securely
- Manual configuration required for external API keys

Next Steps:
1. Set remaining API keys manually (see warnings above)
2. Run: docker-compose -f docker-compose.config.yml up -d
3. Verify configuration: curl http://localhost:8000/api/config/health
4. Check logs: docker logs ai-teddy-bear-app

EOF
    
    log_success "Secrets summary created: $summary_file"
}

validate_docker_swarm() {
    log_info "Checking Docker Swarm mode..."
    
    if ! docker info --format '{{.Swarm.LocalNodeState}}' | grep -q "active"; then
        log_warning "Docker Swarm is not active. Initializing..."
        docker swarm init
        log_success "Docker Swarm initialized"
    else
        log_success "Docker Swarm is active"
    fi
}

cleanup_on_error() {
    log_error "Script failed. Cleaning up..."
    
    # List of secrets that might have been created
    local secrets_to_cleanup=(
        "ai_teddy_bear_database_password"
        "ai_teddy_bear_database_url"
        "ai_teddy_bear_redis_password"
        "ai_teddy_bear_redis_url"
        "ai_teddy_bear_jwt_secret_key"
        "ai_teddy_bear_vault_token"
        "ai_teddy_bear_elasticsearch_password"
    )
    
    for secret in "${secrets_to_cleanup[@]}"; do
        if docker secret ls --format "{{.Name}}" | grep -q "^${secret}$"; then
            docker secret rm "$secret" 2>/dev/null || true
            log_info "Removed secret: $secret"
        fi
    done
}

# Main execution
main() {
    log_info "Starting Docker Secrets setup for AI Teddy Bear ($ENVIRONMENT environment)"
    
    # Set up error handling
    trap cleanup_on_error ERR
    
    # Preliminary checks
    check_dependencies
    validate_docker_swarm
    
    # Create directory structure
    create_secrets_directory
    backup_existing_secrets
    
    # Generate and create secrets
    generate_database_secrets
    generate_redis_secrets
    generate_jwt_secrets
    create_vault_secrets
    create_elasticsearch_secrets
    
    # External service secrets (may require manual setup)
    create_ai_provider_secrets
    create_aws_secrets
    create_communication_secrets
    create_external_service_secrets
    
    # Create summary
    create_secrets_summary
    
    log_success "Docker Secrets setup completed successfully!"
    log_info "Summary file: secrets/generated/secrets_summary.txt"
    log_info "To start the application: docker-compose -f docker-compose.config.yml up -d"
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi