"""
Alembic environment for the ERP-owned Postgres database.

This intentionally does NOT import the Flask app: migrations must be runnable
during deploy without the AutoCount SDK bridge or a live SQL Server. It only
needs the model metadata and a database URL.

The URL comes from, in order of precedence:
  1. -x db_url=... on the alembic command line
  2. the DATABASE_URL environment variable (the same one the app reads)
  and is required -- there is no local fallback.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Loads .env the same way function/config.py does, so a DATABASE_URL set there
# also applies to migrations.
from function.config import load_env_file  # noqa: E402

load_env_file(BASE_DIR / ".env")

# Importing the package registers every model on db.metadata.
from models import db  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = db.metadata


def get_url():
    from_cli = context.get_x_argument(as_dictionary=True).get("db_url")
    if from_cli:
        return from_cli
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Migrations run against Postgres only; "
            "pass -x db_url=... to override."
        )
    return url


def run_migrations_offline():
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite cannot ALTER most things in place; batch mode rewrites the
        # table instead. Harmless on Postgres.
        render_as_batch=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
