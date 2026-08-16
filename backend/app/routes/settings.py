"""Settings routes — GET and PATCH the single settings row."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.settings_service import get_settings, update_settings
from app.schemas.schemas import SettingsOut, SettingsUpdate

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
def patch_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    """PATCH /api/settings — Partial update to settings.

    Args:
        payload: SettingsUpdate with fields to change (id ignored if present)

    Returns:
        SettingsOut: Updated settings row

    Raises:
        422: Validation error (e.g., tax_rate out of bounds)
        500: if settings row is missing
    """
    return update_settings(db, payload)
