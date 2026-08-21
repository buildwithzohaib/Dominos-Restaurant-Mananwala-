"""Settings routes — GET and PATCH the single settings row, plus backup restore."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db, BACKEND_DIR, DB_PATH, engine
from app.models.models import User
from app.services.settings_service import get_settings, update_settings
from app.services.backup_service import get_backup_dir, restore_database
from app.schemas.schemas import SettingsOut, SettingsUpdate
from app.routes.auth import require_permission

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db)):
    """GET /api/settings — Fetch the single settings row.

    Returns:
        SettingsOut: The settings row (id=1, always present after migration)

    Raises:
        500: if settings row is missing (migration not run)
    """
    return get_settings(db)


@router.patch("", response_model=SettingsOut)
def patch_settings(payload: SettingsUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("can_manage_settings"))):
    """PATCH /api/settings — Partial update to settings.

    Requires can_manage_settings permission or is_owner status.

    Args:
        payload: SettingsUpdate with fields to change (id ignored if present)

    Returns:
        SettingsOut: Updated settings row

    Raises:
        403: if user lacks can_manage_settings permission and is not owner
        422: Validation error (e.g., tax_rate out of bounds)
        500: if settings row is missing
    """
    return update_settings(db, payload)


@router.post("/backup/restore")
def restore_from_backup(current_user: User = Depends(require_permission("can_manage_settings"))):
    """POST /api/settings/backup/restore — Restore database from most recent backup.

    Requires can_manage_settings permission or is_owner status.

    WARNING: This overwrites the current database. All data since the backup was taken is lost.
    The server MUST be restarted for the restore to take effect.

    Returns:
        dict with keys:
        - success: bool
        - message: str (user-facing message)
        - backup_date: str (ISO date, e.g., "2026-08-20")
        - safety_backup: str (filename of pre-restore safety backup, e.g., "pos_before_restore_2026-08-20T143022.db")
        - restart_required: bool (always True on success)
        - error: str (only on failure)

    Raises:
        403: if user lacks can_manage_settings permission and is not owner
        None (all errors returned in response dict)
    """
    backup_dir = get_backup_dir(BACKEND_DIR)
    return restore_database(DB_PATH, backup_dir, engine)
