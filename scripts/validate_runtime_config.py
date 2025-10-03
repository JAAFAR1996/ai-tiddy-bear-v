#!/usr/bin/env python3
"""
Production-ready runtime configuration validator.

Runs before starting the server to ensure all required environment
variables are present and valid. Exits with code 1 on failure.

Usage: python3 scripts/validate_runtime_config.py

This script uses the unified ProductionConfig which already reads from:
1) Process environment variables
2) .env file in project root (if present)
"""
from __future__ import annotations

import sys


def main() -> int:
    try:
        from src.infrastructure.config.production_config import load_config

        # Reads ENV + .env automatically via Pydantic Settings
        cfg = load_config()
        # Minimal success line for logs
        print(
            f"CONFIG OK: ENV={cfg.ENVIRONMENT}, CORS={len(cfg.CORS_ALLOWED_ORIGINS)}, HOSTS={len(cfg.ALLOWED_HOSTS)}"
        )
        return 0
    except Exception as e:  # production_config logs details already
        print(f"CONFIG ERROR: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
