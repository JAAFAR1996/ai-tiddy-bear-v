# AI Teddy Bear - Production Docker Image for Render.com
# ===================================================
FROM python:3.11-slim

LABEL maintainer="AI Teddy Bear Team <team@aiteddybear.com>" \
      version="1.0.0" \
      description="AI Teddy Bear Production Container for Render" \
      security.scan.enabled="true" \
      coppa.compliant="true" \
      child.safety.validated="true"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    PYTHONPATH="/app/src" \
    ENVIRONMENT=production \
    COPPA_COMPLIANCE_MODE=1 \
    CHILD_SAFETY_STRICT=1
 

# non-root user
RUN groupadd -r -g 1000 appuser && useradd -r -u 1000 -g appuser -s /bin/false -c "Application User" appuser

WORKDIR /app

# OS deps: ثبّت أدوات البناء الآن، ونظّف بعد pip
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libmagic1 curl ca-certificates dumb-init procps netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --compile -r requirements.txt && \
    apt-get purge -y --auto-remove build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /var/cache/apt/*

# app code + Alembic files for database migrations
COPY --chown=appuser:appuser src/ ./src
COPY --chown=appuser:appuser entrypoint.sh .
COPY --chown=appuser:appuser alembic.ini .
COPY --chown=appuser:appuser migrations/ ./migrations/
COPY --chown=appuser:appuser scripts/ ./scripts/

# FS prep & perms (including migration script)
RUN chmod 0755 /app/entrypoint.sh && \
    chmod +x /app/scripts/migrate-and-start.sh && \
    mkdir -p /app/logs /app/uploads /app/temp /app/data /app/secure_storage && \
    chown -R appuser:appuser /app && \
    chmod 750 /app/logs /app/uploads /app/temp /app/data && \
    chmod 700 /app/secure_storage && \
    find /app -type f -name "*.pyc" -delete && \
    find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

USER appuser

# Health check with extended timeout for migration period
HEALTHCHECK --interval=30s --timeout=120s --start-period=180s --retries=3 \
  CMD curl -fsS http://localhost:${PORT:-8000}/health || exit 1

EXPOSE 8000

# Use flexible entrypoint that supports command passthrough
ENTRYPOINT ["dumb-init", "--", "/app/entrypoint.sh"]

# Default command: run migrations and start server
CMD ["bash", "/app/scripts/migrate-and-start.sh"]
