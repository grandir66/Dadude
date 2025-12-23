"""
DaDude v2.0 - Alembic Environment Configuration
Async PostgreSQL migrations support
"""
import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine

from alembic import context

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import all models to ensure they are registered with Base.metadata
# This is crucial for autogenerate to detect all tables
from app.models.database import Base
from app.models.database import (
    Customer, Network, Credential, CustomerCredentialLink,
    DeviceAssignment, AlertHistory, AgentAssignment,
    ScanResult, DiscoveredDevice
)
from app.models.inventory import (
    InventoryDevice, NetworkInterface, DiskInfo,
    InstalledSoftware, ServiceInfo, WindowsDetails,
    LinuxDetails, MikroTikDetails, NetworkDeviceDetails,
    NetwatchConfig, DudeAgent
)
from app.models.backup_models import (
    DeviceBackup, BackupSchedule, BackupJob, BackupTemplate
)

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata

# Database URL from environment
def get_url():
    """Get database URL from environment or config"""
    url = os.getenv("DATABASE_URL_SYNC")
    if url:
        return url

    url = os.getenv("DATABASE_URL")
    if url:
        # Convert async URL to sync for Alembic
        return url.replace("+asyncpg", "")

    # Default for local development
    return "postgresql://dadude:dadude_secret@localhost:5432/dadude"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with given connection"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine"""
    url = get_url()

    # Use async engine for PostgreSQL
    connectable = create_async_engine(
        url.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # For PostgreSQL, we can use sync connection for migrations
    from sqlalchemy import create_engine

    url = get_url()
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
