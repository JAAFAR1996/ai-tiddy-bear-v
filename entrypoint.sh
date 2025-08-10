#!/bin/bash

# Render-compatible entrypoint for AI Teddy Bear
set -e

# Start FastAPI app with Uvicorn (single worker for Render)
uvicorn src.main:app --host 0.0.0.0 --port 10000
