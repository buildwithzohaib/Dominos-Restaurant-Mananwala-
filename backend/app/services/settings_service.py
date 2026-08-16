"""Settings business logic — fetch and update the single settings row."""
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import Settings
from app.schemas.schemas import SettingsUpdate


def get_settings(db: Session) -> Settings:
    """Fetch the single settings row (id=1).

    Raises:
        RuntimeError: if the row is missing (migration not run).
    """
    row = db.query(Settings).filter(Settings.id == 1).first()
    if not row:
        raise RuntimeError("Settings row missing. Run: alembic upgrade head")
    return row


def update_settings(db: Session, updates: SettingsUpdate) -> Settings:
    """Partial update to settings. id cannot be changed.

    Args:
        db: database session
        updates: SettingsUpdate with fields to change (id ignored if present)

    Returns:
        Updated Settings row

    Raises:
        RuntimeError: if settings row is missing
    """
    row = get_settings(db)

    # Extract update fields, excluding id if someone tries to pass it
    update_data = updates.model_dump(exclude_unset=True)
    update_data.pop("id", None)  # Remove id if present; cannot update it

    # Apply updates
    for key, value in update_data.items():
        setattr(row, key, value)

    # Explicit updated_at
    row.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(row)
    return row
