# AI Teddy Bear - Production Docker Image for Render.com
# ===================================================
# Optimized single-stage build with libmagic support for Render deployment

FROM python:3.13-slim

# Security and production labels
LABEL maintainer="AI Teddy Bear Team <team@aiteddybear.com>" \
      version="1.0.0" \
      description="AI Teddy Bear Production Container for Render" \
      security.scan.enabled="true" \
      coppa.compliant="true" \
      child.safety.validated="true"

# Environment variables for production optimization
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH="/app/src" \
    ENVIRONMENT=production \
    COPPA_COMPLIANCE_MODE=1 \
    CHILD_SAFETY_STRICT=1

# Security: Create non-root user early
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -s /bin/false -c "Application User" appuser

# Install system dependencies including libmagic (CRITICAL for file validation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    build-essential \
    netcat-openbsd \
    curl \
    ca-certificates \
    dumb-init \
    procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /var/cache/apt/*

# Set working directory
WORKDIR /app

# Copy requirements first for optimal Docker layer caching
COPY requirements.txt .

# Install Python dependencies with security optimizations
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --compile -r requirements.txt

# Copy application code with proper ownership
COPY --chown=appuser:appuser . .

# Fix entrypoint permissions and create necessary directories
RUN chmod +x docker-entrypoint.sh && \
    mkdir -p logs uploads temp data secure_storage && \
    chown -R appuser:appuser /app && \
    chmod 750 logs uploads temp data && \
    chmod 700 secure_storage

# Security cleanup: Remove potential attack vectors
RUN find /app -type f -name "*.pyc" -delete && \
    find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Switch to non-root user for security
USER appuser

# Health check for Render monitoring (endpoint must exist and be lightweight)
HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Render.com automatically provides $PORT environment variable
# Default port for local development
EXPOSE 8000


# انسخ السكربت وفعّله
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# استخدم dumb-init + entrypoint الذي يفرض التوسعة
ENTRYPOINT ["dumb-init", "--", "/app/entrypoint.sh"]

# اترك CMD كسطر واحد؛ entrypoint سيشغّله عبر sh -c ويوسّع ${PORT}
CMD ["gunicorn -k uvicorn.workers.UvicornWorker src.main:app \
    --workers 1 --bind 0.0.0.0:${PORT:-8000} \
    --timeout 120 --keep-alive 2 \
    --max-requests 1000 --max-requests-jitter 50 \
    --access-logfile - --error-logfile -"]
