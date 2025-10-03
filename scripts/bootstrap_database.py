#!/usr/bin/env python3
"""Idempotent database bootstrap for core AI Teddy Bear schema.

Creates ORM-defined tables before Alembic migrations execute so that
fresh deployments have a complete baseline without relying on fragile SQL dumps.
"""

from __future__ import annotations

import logging
import os
from importlib import import_module
from typing import Iterable, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from src.core.exceptions import ConfigurationError
from src.infrastructure.config.config_manager_provider import get_config_manager

logger = logging.getLogger("bootstrap_database")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

MetadataSource = Tuple[str, object]


def _get_database_url() -> str:
    candidates = [
        os.getenv("MIGRATIONS_DATABASE_URL"),
        os.getenv("DATABASE_URL"),
    ]
    for url in candidates:
        if url:
            return url
    raise RuntimeError("DATABASE_URL not configured")


def _is_postgres(engine: Engine) -> bool:
    return engine.dialect.name.startswith("postgres")


def _ensure_extensions(engine: Engine) -> None:
    if not _is_postgres(engine):
        logger.info("Skipping extension setup for %s", engine.dialect.name)
        return

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))


def _load_configuration():
    config_manager = get_config_manager()
    load_config_fn = getattr(config_manager, "load_config", None)
    if load_config_fn is None:
        logger.warning("Config manager does not expose load_config(); skipping preload")
        return config_manager

    env_file = os.getenv("ENV_FILE")
    kwargs = {"env_file": env_file} if env_file else {}

    try:
        load_config_fn(**kwargs)
    except TypeError:
        # Fallback for implementations that do not accept keyword arguments
        if env_file:
            load_config_fn(env_file)
        else:
            load_config_fn()

    return config_manager


def _discover_metadata(config_manager) -> Iterable[MetadataSource]:
    seen_tables = set()
    modules = (
        "src.infrastructure.database.models",
    )

    for module_path in modules:
        try:
            module = import_module(module_path)
        except ImportError as exc:
            logger.debug("Skipping %s: %s", module_path, exc)
            continue

        if hasattr(module, "config_manager"):
            setattr(module, "config_manager", config_manager)

        base = getattr(module, "Base", None)
        metadata = getattr(base, "metadata", None)
        if metadata is None:
            logger.debug("Module %s has no SQLAlchemy Base metadata", module_path)
            continue

        table_names = set(metadata.tables.keys())
        if not table_names:
            logger.debug("Module %s has no tables to create", module_path)
            continue

        if table_names.issubset(seen_tables):
            logger.debug("Tables from %s already handled; skipping", module_path)
            continue

        seen_tables.update(table_names)
        yield module_path, metadata


def bootstrap_schema(database_url: Optional[str] = None) -> None:
    url = database_url or _get_database_url()
    logger.info("Bootstrapping database schema using %s", url)

    config_manager = _load_configuration()

    engine = create_engine(url, future=True)
    try:
        _ensure_extensions(engine)

        metadata_sources = list(_discover_metadata(config_manager))
        if not metadata_sources:
            logger.warning("No metadata sources discovered; nothing to bootstrap")
            return

        with engine.begin() as connection:
            for module_path, metadata in metadata_sources:
                logger.info("Ensuring tables for %s", module_path)
                metadata.create_all(connection, checkfirst=True)

        logger.info("Schema bootstrap complete")
    except (SQLAlchemyError, ConfigurationError) as exc:
        logger.error("Schema bootstrap failed: %s", exc)
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    bootstrap_schema()
