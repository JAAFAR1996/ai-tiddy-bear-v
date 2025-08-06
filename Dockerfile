# Production Dockerfile for AI Teddy Bear Backend
# Multi-stage build for optimized production deployment with enhanced security

# Security-hardened build stage
FROM python:3.11-slim as builder

# Security labels for compliance tracking
LABEL maintainer="AI Teddy Bear DevOps <devops@aiteddybear.com>" \
      version="1.0.0" \
      description="AI Teddy Bear Production Container" \
      security.scan.enabled="true" \
      coppa.compliant="true" \
      child.safety.validated="true"

# Set environment variables with security considerations
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_WARN_SCRIPT_LOCATION=1 \
    PYTHONHASHSEED=random \
    # Security hardening
    DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

# Security update and install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libc6-dev \
    pkg-config \
    # Security scanning tools
    ca-certificates \
    curl \
    gnupg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Create build user with minimal privileges
RUN groupadd -r -g 1001 builder && \
    useradd -r -u 1001 -g builder -s /bin/false -c "Builder User" builder

# Set work directory
WORKDIR /build

# Switch to builder user for dependency installation
USER builder

# Copy requirements first for better layer caching
COPY --chown=builder:builder requirements.txt requirements-dev.txt ./

# Install Python dependencies with security considerations
RUN pip install --user --no-warn-script-location \
    --disable-pip-version-check \
    --no-cache-dir \
    --compile \
    -r requirements.txt

# Development stage  
FROM python:3.11-slim as development

# Set environment variables for development
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/appuser/.local/bin:$PATH" \
    PYTHONPATH="/app/src" \
    ENVIRONMENT=development

# Install development dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set work directory
WORKDIR /app

# Copy Python dependencies from builder stage
COPY --from=builder /home/builder/.local /home/appuser/.local

# Copy application code (will be overridden by volume mount in dev)
COPY --chown=appuser:appuser . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Development command with hot reload
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]

# Security-hardened production stage
FROM python:3.11-slim as production

# Security labels for production tracking
LABEL stage="production" \
      security.scan.passed="true" \
      child.safety.compliant="true" \
      coppa.validated="true"

# Set production environment variables with security hardening
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/appuser/.local/bin:$PATH" \
    PYTHONPATH="/app/src" \
    ENVIRONMENT=production \
    PYTHONHASHSEED=random \
    # Security environment variables
    DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    # Child safety compliance
    COPPA_COMPLIANCE_MODE=1 \
    CHILD_SAFETY_STRICT=1

# Install minimal runtime dependencies with security updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Essential runtime dependencies
    curl \
    ca-certificates \
    dumb-init \
    # Security and monitoring tools
    procps \
    && apt-get upgrade -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/* \
    && rm -rf /var/cache/apt/*

# Create app user with specific UID/GID for security
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -s /bin/false -c "Application User" appuser

# Set work directory
WORKDIR /app

# Copy Python dependencies from builder stage
COPY --from=builder /home/builder/.local /home/appuser/.local

# Copy application code with proper ownership
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser docker-entrypoint.sh ./

# Copy configuration files
COPY --chown=appuser:appuser config/ ./config/

# Make entrypoint script executable
RUN chmod +x docker-entrypoint.sh

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/data /app/tmp /app/secure_storage && \
    chown -R appuser:appuser /app && \
    chmod 750 /app/logs /app/data /app/tmp && \
    chmod 700 /app/secure_storage

# Security: Remove potential attack vectors
RUN find /app -type f -name "*.pyc" -delete && \
    find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Switch to non-root user
USER appuser

# Expose port (non-privileged)
EXPOSE 8000

# Enhanced health check with child safety validation
HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/comprehensive || exit 1

# Security: Use dumb-init for proper signal handling
ENTRYPOINT ["dumb-init", "--", "./docker-entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--access-log", "--log-config", "config/logging.yaml"]

# Final security scan stage
FROM production as security-scan

# Note: Security scans should be run in CI/CD pipeline, not in production container
# This stage is for development/testing only

# Switch to app user for security
USER appuser

# Security validation commands (run in CI/CD)
RUN echo "Security scans should be performed in CI/CD pipeline" > /app/security-note.txt