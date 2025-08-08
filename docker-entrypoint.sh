#!/usr/bin/env bash
set -Eeuo pipefail

echo "🧸 AI Teddy Bear V5 - Starting Application"
echo "Environment: ${ENVIRONMENT:-development}"
echo "Debug Mode: ${DEBUG:-false}"

wait_for_service() {
  local host=$1
  local port=$2
  local service_name=$3
  local max_attempts=30
  local attempt=1

  echo "⏳ Waiting for $service_name at $host:$port..."
  while ! nc -z "$host" "$port" 2>/dev/null; do
    if [ $attempt -eq $max_attempts ]; then
      echo "❌ Failed to connect to $service_name after $max_attempts attempts"
      exit 1
    fi
    echo "⏳ Attempt $attempt/$max_attempts - $service_name not ready, waiting..."
    sleep 2
    attempt=$((attempt + 1))
  done
  echo "✅ $service_name is ready!"
}

validate_config() {
  echo "🔍 Validating configuration..."
  if [ "${ENVIRONMENT:-}" = "production" ]; then
    local required_vars=(
      SECRET_KEY
      JWT_SECRET_KEY
      COPPA_ENCRYPTION_KEY
      DATABASE_URL
      REDIS_URL
      OPENAI_API_KEY
      PARENT_NOTIFICATION_EMAIL
    )
    local missing_vars=()
    for var in "${required_vars[@]}"; do
      if [ -z "${!var:-}" ]; then
        missing_vars+=("$var")
      fi
    done
    if [ ${#missing_vars[@]} -ne 0 ]; then
      echo "❌ Missing required environment variables:"
      printf '%s\n' "${missing_vars[@]}"
      echo ""
      echo "Please set all required environment variables before starting."
      exit 1
    fi
    if [ ${#SECRET_KEY} -lt 32 ]; then
      echo "❌ SECRET_KEY must be at least 32 characters long"; exit 1; fi
    if [ ${#JWT_SECRET_KEY} -lt 32 ]; then
      echo "❌ JWT_SECRET_KEY must be at least 32 characters long"; exit 1; fi
    if [ ${#COPPA_ENCRYPTION_KEY} -lt 32 ]; then
      echo "❌ COPPA_ENCRYPTION_KEY must be at least 32 characters long"; exit 1; fi
  fi
  echo "✅ Configuration validation passed!"
}

show_startup_info() {
  echo ""
  echo "🧸 AI Teddy Bear V5 - Startup Information"
  echo "=========================================="
  echo "Environment: ${ENVIRONMENT:-development}"
  echo "Debug Mode: ${DEBUG:-false}"
  echo "Log Level: ${LOG_LEVEL:-INFO}"
  echo "Host: ${HOST:-0.0.0.0}"
  echo "Port: ${PORT:-8000}"
  echo "Workers: ${WORKERS:-1}"
  echo "COPPA Compliance: ${COPPA_COMPLIANCE_MODE:-true}"
  echo "Content Filter Strict: ${CONTENT_FILTER_STRICT:-true}"
  echo "=========================================="
  echo ""
}

main() {
  show_startup_info
  validate_config
  echo "🚀 Starting application with command: $*"
  echo ""
  exec "$@"
}

if [ "${1:-}" = "check" ]; then
  echo "🔍 Running configuration check..."
  validate_config
  echo "✅ All checks passed!"
  exit 0
else
  main "$@"
fi
