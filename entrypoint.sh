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

# Execute passed command or default behavior
if [ $# -eq 0 ]; then
    echo "No command specified, running default startup"
    exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
else
    echo "Executing command: $@"
    exec "$@"
fi
