"""Database backup and restore operations (Stage 9).

Backup runs daily on startup if today's backup doesn't already exist.
Restores always pick the most recent backup and require server restart.
Safety backups (pre-restore snapshots) are kept indefinitely.
"""
import os
import shutil
import glob
from datetime import datetime, date, timedelta
from sqlalchemy import Engine


def get_backup_dir(backend_dir: str) -> str:
    """Return absolute path to backups directory, creating it if needed."""
    backup_dir = os.path.join(backend_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def create_backup(db_path: str, backup_dir: str) -> tuple[bool, str]:
    """
    Create a backup of pos.db if today's backup doesn't already exist.

    Args:
        db_path: Absolute path to pos.db
        backup_dir: Absolute path to backups/ directory

    Returns:
        (created: bool, backup_path: str)
        created=True if backup was created this run
        created=False if today's backup already existed
        backup_path is the absolute path to the backup file (regardless of whether created)

    Raises:
        OSError if the backup operation fails (e.g., no write permission)
    """
    os.makedirs(backup_dir, exist_ok=True)

    today = date.today().isoformat()  # "2026-08-20"
    backup_path = os.path.join(backup_dir, f"pos_{today}.db")

    # Check file system: does today's backup already exist?
    if os.path.exists(backup_path):
        return False, backup_path  # Already backed up today

    # Create backup via copy
    shutil.copy2(db_path, backup_path)
    return True, backup_path


def cleanup_old_backups(backup_dir: str, keep_days: int = 30) -> list[str]:
    """
    Delete daily backups older than keep_days.
    Never deletes pos_before_restore_* (safety backups from restores).

    Args:
        backup_dir: Absolute path to backups/ directory
        keep_days: Number of days to retain (default 30)

    Returns:
        List of absolute paths to deleted files (empty if none deleted or dir doesn't exist)
    """
    if not os.path.isdir(backup_dir):
        return []  # Backups directory doesn't exist yet

    cutoff = date.today() - timedelta(days=keep_days)
    deleted = []

    # List all pos_YYYY-MM-DD.db files (NOT pos_before_restore_* files)
    for backup_file in glob.glob(os.path.join(backup_dir, "pos_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].db")):
        try:
            # Extract date string from filename "pos_2026-08-20.db"
            basename = os.path.basename(backup_file)
            date_str = basename[4:14]  # Characters 4-14: "2026-08-20"
            file_date = date.fromisoformat(date_str)

            if file_date < cutoff:
                os.remove(backup_file)
                deleted.append(backup_file)
        except (ValueError, OSError):
            # Malformed filename or delete failed; skip
            pass

    return deleted


def get_recent_backup_path(backup_dir: str) -> str | None:
    """
    Find the most recent daily backup file.
    Ignores pos_before_restore_* files.

    Args:
        backup_dir: Absolute path to backups/ directory

    Returns:
        Absolute path to the most recent pos_YYYY-MM-DD.db file, or None if none found
    """
    if not os.path.isdir(backup_dir):
        return None

    backup_files = glob.glob(os.path.join(backup_dir, "pos_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].db"))

    if not backup_files:
        return None

    # Sort by filename (ISO dates sort chronologically); return the last one
    return sorted(backup_files)[-1]


def restore_database(
    db_path: str,
    backup_dir: str,
    engine: Engine,
) -> dict:
    """
    Restore the database from the most recent backup.

    Process:
    1. Verify a backup exists
    2. Create a safety backup of current pos.db before overwriting
    3. Dispose all engine connections (closes file handles)
    4. Copy backup over pos.db
    5. Return response indicating restart is required

    Args:
        db_path: Absolute path to pos.db
        backup_dir: Absolute path to backups/ directory
        engine: SQLAlchemy engine instance (will be disposed, not reconnected)

    Returns:
        dict with keys:
        - success: bool
        - message: str (user-facing message)
        - backup_date: str (ISO date of restored backup) or None
        - safety_backup: str (filename of pre-restore safety backup) or None
        - restart_required: bool (always True on success)
        - error: str (only on failure)

    Raises:
        None (all errors are caught and returned in response)
    """
    # Find most recent backup
    backup_path = get_recent_backup_path(backup_dir)
    if not backup_path:
        return {
            "success": False,
            "message": "No backup files found.",
            "error": "No backup files found.",
            "backup_date": None,
            "safety_backup": None,
            "restart_required": False,
        }

    try:
        # Extract backup date from filename for response
        basename = os.path.basename(backup_path)
        backup_date = basename[4:14]  # "2026-08-20"

        # Create safety backup of current pos.db before overwriting
        if os.path.exists(db_path):
            now_iso = datetime.now().isoformat(timespec="seconds").replace(":", "")  # "20260820T143022"
            safety_backup_name = f"pos_before_restore_{backup_date}T{now_iso[9:]}.db"
            safety_backup_path = os.path.join(backup_dir, safety_backup_name)
            shutil.copy2(db_path, safety_backup_path)
        else:
            safety_backup_name = None

        # Dispose all engine connections (closes SQLite file handles)
        engine.dispose()

        # Atomic file swap: copy backup over pos.db
        shutil.copy2(backup_path, db_path)

        # Return success response with restart flag
        return {
            "success": True,
            "message": f"Database restored from {backup_date}. Server restart required to take effect.",
            "backup_date": backup_date,
            "safety_backup": safety_backup_name,
            "restart_required": True,
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Restore failed: {str(e)}",
            "error": str(e),
            "backup_date": None,
            "safety_backup": None,
            "restart_required": False,
        }
