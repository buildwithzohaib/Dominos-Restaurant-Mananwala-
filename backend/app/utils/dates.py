"""Date/time utilities for business day calculations."""

from datetime import datetime, timedelta, timezone


def get_business_day_boundaries(db_session, now: datetime | None = None) -> tuple[datetime, datetime]:
    """
    Calculate the business day start and end times based on settings.day_starts_at.

    The business day runs from day_starts_at on the current date (or yesterday if we haven't
    reached day_starts_at yet) to day_starts_at on the next date.

    Args:
        db_session: SQLAlchemy session to fetch settings from
        now: Current UTC time (defaults to datetime.now(timezone.utc) if not provided)

    Returns:
        Tuple of (business_day_start, business_day_end) both as UTC datetime objects

    Example:
        If day_starts_at="06:00" and now=2026-08-19T14:30:00Z (after 06:00):
            → returns (2026-08-19T06:00:00Z, 2026-08-20T06:00:00Z)

        If day_starts_at="06:00" and now=2026-08-19T02:00:00Z (before 06:00):
            → returns (2026-08-18T06:00:00Z, 2026-08-19T06:00:00Z)
    """
    if now is None:
        # Use datetime.now(timezone.utc) to avoid deprecated utcnow(), then strip tzinfo
        # to keep all datetimes naive (matching the rest of the codebase which uses utcnow())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        # If caller passed in an aware datetime, strip tzinfo for consistency
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)

    # Fetch settings to get day_starts_at
    from app.models.models import Settings

    settings = db_session.query(Settings).first()
    if not settings:
        # Fallback to default if settings don't exist (shouldn't happen in normal operation)
        day_starts_at = "06:00"
    else:
        day_starts_at = settings.day_starts_at

    # Parse HH:MM format
    hour_str, minute_str = day_starts_at.split(":")
    boundary_hour = int(hour_str)
    boundary_minute = int(minute_str)

    # Create a datetime at the boundary time for today (in UTC)
    boundary_time = now.replace(hour=boundary_hour, minute=boundary_minute, second=0, microsecond=0)

    # Determine if we're before or after the boundary
    if now >= boundary_time:
        # We're on or after the boundary — business day started today
        business_day_start = boundary_time
        business_day_end = boundary_time + timedelta(days=1)
    else:
        # We're before the boundary — business day started yesterday
        business_day_start = boundary_time - timedelta(days=1)
        business_day_end = boundary_time

    return business_day_start, business_day_end
