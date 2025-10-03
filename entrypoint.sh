#!/bin/bash

# AI Teddy Bear - Production Entrypoint
# Flexible entrypoint that supports command passthrough
set -e

echo "🧸 AI Teddy Bear - Container Starting"
echo "===================================="

# Environment info
echo "User: $(whoami)"
echo "Working Directory: $(pwd)"
echo "Environment: ${ENVIRONMENT:-production}"

# Helper: load env var from Docker secret file if present
load_secret() {
    # Usage: load_secret ENV_VAR [SECRET_FILE_NAME]
    local var_name="$1"
    local secret_name="${2:-}"
    local file_var_name="${var_name}_FILE"

    # Prefer explicit *_FILE path
    if [ -n "${!file_var_name:-}" ] && [ -f "${!file_var_name}" ]; then
        export "$var_name"="$(tr -d '\r\n' < "${!file_var_name}")"
        return
    fi

    # Fallback to /run/secrets/<secret_name>
    if [ -n "$secret_name" ] && [ -f "/run/secrets/${secret_name}" ]; then
        export "$var_name"="$(tr -d '\r\n' < "/run/secrets/${secret_name}")"
        return
    fi
}

if [ "${DOCKER_SECRETS_DISABLED:-false}" = "true" ]; then
    echo "Docker secrets loading disabled via DOCKER_SECRETS_DISABLED=true"
else
    # Load common secrets into env if available
    # Core app secrets
    load_secret SECRET_KEY ai_teddy_bear_secret_key
    load_secret JWT_SECRET_KEY ai_teddy_bear_jwt_secret_key
    load_secret COPPA_ENCRYPTION_KEY ai_teddy_bear_coppa_encryption_key
    load_secret JWT_PRIVATE_KEY ai_teddy_bear_jwt_private_key
    load_secret JWT_PUBLIC_KEY ai_teddy_bear_jwt_public_key
    load_secret ENCRYPTION_KEY ai_teddy_bear_encryption_key

    # External services
    load_secret OPENAI_API_KEY ai_teddy_bear_openai_api_key
    load_secret ELEVENLABS_API_KEY ai_teddy_bear_elevenlabs_api_key
    load_secret STRIPE_SECRET_KEY ai_teddy_bear_stripe_api_key
    load_secret STRIPE_PUBLISHABLE_KEY ai_teddy_bear_stripe_publishable_key
    load_secret STRIPE_WEBHOOK_SECRET ai_teddy_bear_stripe_webhook_secret
    load_secret SENTRY_DSN ai_teddy_bear_sentry_dsn

    # Data services
    load_secret DATABASE_URL ai_teddy_bear_database_url
    load_secret REDIS_URL ai_teddy_bear_redis_url
fi

# Execute passed command or default behavior
if [ $# -eq 0 ]; then
    echo "No command specified, running default startup"
    # Use module-level app instance defined in src/main.py
    exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
else
    echo "Executing command: $@"
    exec "$@"
fi
