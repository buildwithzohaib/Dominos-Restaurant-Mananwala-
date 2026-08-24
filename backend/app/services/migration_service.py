"""Database migration service (automatic migration at startup).

Safely runs pending migrations on startup using Alembic's Python API.
Pre-migration backups are created and logged. On failure, the app refuses to start.

A rotating file log (pos.log) is kept in the data directory to provide a
permanent record of migrations and startup events on client machines.
"""
import os
import shutil
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from alembic.migration import MigrationContext
from alembic.command import upgrade as alembic_upgrade
from app.database import get_resource_base

# Use uvicorn's error logger so messages appear in console alongside uvicorn's own output
logger = logging.getLogger("uvicorn.error")


def setup_file_logging(data_dir: str) -> None:
    """
    Set up a rotating file logger for migrations and startup events.

    Creates a pos.log file in the data directory with a rotating handler.
    Keeps up to 3 backups, each up to 1 MB, for a total of ~4 MB of history.

    Args:
        data_dir: Path to the data directory (where pos.db lives)
    """
    os.makedirs(data_dir, exist_ok=True)
    log_path = os.path.join(data_dir, "pos.log")

    # Create a rotating file handler: 1 MB per file, keep 3 backups
    # Backups are named pos.log.1, pos.log.2, pos.log.3
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=1024 * 1024,  # 1 MB
        backupCount=3,
    )

    # Format: timestamp [LEVEL] message
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)

    # Add handler to the uvicorn.error logger
    logger.addHandler(file_handler)

    # Ensure handler sees INFO and above
    file_handler.setLevel(logging.INFO)
    logger.setLevel(logging.INFO)


def get_current_revision(engine: Engine) -> str | None:
    """
    Get the current migration revision using Alembic's MigrationContext.

    IMPORTANT: This opens a connection, reads the revision, and IMMEDIATELY closes it.
    The connection must be closed before alembic runs its own upgrade, or SQLite
    will lock with "database is locked" because SQLite allows only one writer.

    Args:
        engine: SQLAlchemy engine

    Returns:
        Current revision string (e.g., "abc123def456"), or None if alembic_version table doesn't exist
    """
    try:
        with engine.connect() as conn:
            # Use Alembic's MigrationContext to get the current revision
            # This is the proper way to query alembic_version
            ctx = MigrationContext.configure(conn)
            return ctx.get_current_revision()
    except Exception:
        # Table doesn't exist or error reading it (fresh database)
        return None


def get_head_revision(alembic_dir: str) -> str:
    """
    Get the head (latest) migration revision.

    Args:
        alembic_dir: Path to alembic directory (e.g., backend/alembic)

    Returns:
        Head revision string (e.g., "abc123def456"), or None if no migrations exist
    """
    # ScriptDirectory reads from alembic/versions/ to find all migrations
    script = ScriptDirectory(alembic_dir)
    return script.get_current_head()


def create_premigration_backup(db_path: str, backup_dir: str) -> str:
    """
    Create a pre-migration backup with a timestamp.

    Args:
        db_path: Absolute path to pos.db
        backup_dir: Absolute path to backups/ directory

    Returns:
        Absolute path to the backup file

    Raises:
        OSError if backup fails
    """
    os.makedirs(backup_dir, exist_ok=True)

    # Create timestamped filename: pos_before_migration_2026-08-20T143022.db
    now_iso = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    backup_filename = f"pos_before_migration_{now_iso}.db"
    backup_path = os.path.join(backup_dir, backup_filename)

    shutil.copy2(db_path, backup_path)
    return backup_path


def run_migrations(db_path: str, backup_dir: str, engine: Engine, alembic_dir: str) -> None:
    """
    Run pending migrations safely, with pre-migration backup and error handling.

    Process:
    1. Check if already at head (fast path: do nothing)
    2. If behind:
       a. Create pre-migration backup
       b. Log which revision we're on and moving to
       c. Run upgrade
       d. Log success
    3. If upgrade raises, log failure loudly and re-raise

    Args:
        db_path: Absolute path to pos.db
        backup_dir: Absolute path to backups/ directory
        engine: SQLAlchemy engine
        alembic_dir: Absolute path to alembic/ directory (e.g., backend/alembic)

    Raises:
        Exception: If migration fails (logged before re-raising)
    """
    # Get current and head revisions
    current = get_current_revision(engine)
    head = get_head_revision(alembic_dir)

    # CRITICAL: Dispose the engine connection pool after revision check.
    # get_current_revision() opened a connection to read alembic_version.
    # We must close it (and any pooled connections) before alembic runs its upgrade,
    # or SQLite will deadlock with "database is locked" (only one writer allowed).
    engine.dispose()

    # Fast path: already at head (or no migrations exist and DB is fresh)
    if current == head:
        if head is None:
            logger.info("App started. No migrations in system (fresh codebase).")
        else:
            logger.info(f"App started. Database at head revision: {head[:8]}...")
        return

    # Log current state before running migration
    if current is None:
        logger.info(
            f"App started. Database has no migration history (fresh install).\n"
            f"  Running all migrations to reach head: {head[:8]}..."
        )
    else:
        logger.info(
            f"App started. Database at revision: {current[:8]}...\n"
            f"  Upgrading to head: {head[:8]}..."
        )

    # Take pre-migration backup BEFORE anything else
    backup_path = None
    try:
        backup_path = create_premigration_backup(db_path, backup_dir)
        logger.info(f"Pre-migration backup created at: {backup_path}")
    except Exception as e:
        logger.error(f"FAILED to create pre-migration backup: {e}")
        raise

    # Run migration
    try:
        # Locate alembic.ini (should be in parent of alembic_dir, e.g., backend/alembic.ini)
        alembic_ini_path = Path(alembic_dir).parent / "alembic.ini"
        if not alembic_ini_path.exists():
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini_path}")

        # Create Alembic config pointing to the alembic.ini
        # IMPORTANT: configure_logger=False tells alembic/env.py to skip fileConfig(),
        # which prevents logging reconfiguration that would disable existing loggers
        # (including uvicorn's) during startup.
        alembic_cfg = AlembicConfig(str(alembic_ini_path), attributes={"configure_logger": False})
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

        # Run upgrade to head. Alembic's env.py will create its own connection
        # via engine_from_config(), so we do NOT pass an open connection.
        alembic_upgrade(alembic_cfg, "head")

        # CRITICAL: Dispose the engine again after migration completes.
        # Alembic has modified the schema, and we want our app's connections
        # to start fresh against the migrated database.
        engine.dispose()

        logger.info(f"Migration completed successfully. Database now at head revision: {head[:8]}...")

    except Exception as e:
        error_msg = (
            f"MIGRATION FAILED. Database integrity may be compromised.\n"
            f"  Error: {e}\n"
            f"  Pre-migration backup: {backup_path}\n"
            f"  Action: Contact support. Do NOT take orders. Restore from backup if needed."
        )
        logger.critical(error_msg)
        raise
