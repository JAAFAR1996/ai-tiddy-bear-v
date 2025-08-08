# AI Teddy Bear - Production Docker Image for Render.com
# ===================================================
FROM python:3.13-slim

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
    PYTHONPATH="/app/src" \
    ENVIRONMENT=production \
    COPPA_COMPLIANCE_MODE=1 \
    CHILD_SAFETY_STRICT=1

# create non-root user
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -s /bin/false -c "Application User" appuser

# deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 curl ca-certificates dumb-init procps netcat-openbsd build-essential \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /var/cache/apt/*

WORKDIR /app

# install python deps
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --compile -r requirements.txt

# copy code
COPY --chown=appuser:appuser . .

# copy entrypoint with correct perms (do this as root)
COPY --chown=appuser:appuser entrypoint.sh /app/entrypoint.sh
RUN chmod 0755 /app/entrypoint.sh && \
    mkdir -p /app/{logs,uploads,temp,data,secure_storage} && \
    chown -R appuser:appuser /app && \
    chmod 750 /app/{logs,uploads,temp,data} && \
    chmod 700 /app/secure_storage && \
    find /app -type f -name "*.pyc" -delete && \
    find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# drop privileges
USER appuser

# healthcheck (route must be lightweight and exist)
HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

EXPOSE 8000

# force shell expansion even if Render overrides CMD
ENTRYPOINT ["dumb-init", "--", "/app/entrypoint.sh"]

# single-string CMD; entrypoint will run it via `sh -c` and expand ${PORT}
CMD ["gunicorn -k uvicorn.workers.UvicornWorker src.main:app \
  --workers 1 --bind 0.0.0.0:${PORT:-8000} \
  --timeout 120 --keep-alive 2 \
  --max-requests 1000 --max-requests-jitter 50 \
  --access-logfile - --error-logfile -"]
