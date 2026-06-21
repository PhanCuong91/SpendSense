from __future__ import annotations
import sys
import os
from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import pool
from sqlalchemy.engine.url import make_url
from alembic import context

# Import Base from your application
from app.db.base import Base
from app.core.config import settings

# Import all models so Alembic can detect them:
from app.db.models.email_raw import EmailRaw
from app.db.models.parsed_candidate import ParsedTransactionCandidate
from app.db.models.event import Event
from app.db.models.correlation_link import CorrelationLink
from app.db.models.error_log import ErrorLog
from app.db.models.audit_log import AuditLog

# Alembic Config
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate
target_metadata = Base.metadata

# Use env var DATABASE_URL if provided
database_url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
is_sqlite = make_url(database_url).get_backend_name() == "sqlite"

def run_migrations_offline():
    """Run migrations in 'offline' mode (SQL scripts)."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode (actual DB)."""
    connect_kwargs = {}
    if is_sqlite:
        connect_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}

    connectable = create_engine(database_url, poolclass=pool.NullPool, **connect_kwargs)

    with connectable.connect() as connection:
        if is_sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()