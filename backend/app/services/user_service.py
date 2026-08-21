"""
User management and authentication service.

Follows existing patterns: validation and business logic isolated from routes,
database operations are transactional, custom exceptions for specific errors.

PIN Storage: bcrypt with cost factor 10. Names are unique case-insensitively.
Sessions: 90-day safety net expiry; no UX timeout. Tokens are session rows in
the database, not in-memory, so server restarts do not lose sessions.
"""

import secrets
from datetime import datetime, timedelta
import bcrypt
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.models import User, UserSession


class UserNotFoundError(ValueError):
    """Raised when a user is not found."""
    pass


class DuplicateNameError(ValueError):
    """Raised when a name already exists (case-insensitive)."""
    pass


class InvalidPINError(ValueError):
    """Raised when PIN is not exactly 4 digits."""
    pass


class AuthenticationFailedError(ValueError):
    """Raised on login failure (name not found or PIN mismatch)."""
    pass


class CannotDeactivateLastOwnerError(ValueError):
    """Raised when trying to deactivate the last active owner."""
    pass


def _hash_pin(pin: str) -> str:
    """Hash a PIN with bcrypt cost factor 10."""
    return bcrypt.hashpw(pin.encode('utf-8'), bcrypt.gensalt(rounds=10)).decode('utf-8')


def _verify_pin(pin: str, hashed: str) -> bool:
    """Verify a PIN against a bcrypt hash."""
    return bcrypt.checkpw(pin.encode('utf-8'), hashed.encode('utf-8'))


def _name_exists_case_insensitive(db: Session, name: str, exclude_user_id: int | None = None) -> bool:
    """
    Check if a name exists (case-insensitive).

    Deliberately includes deactivated users: a departed staff member's name
    stays reserved so that historical order attribution can never become
    ambiguous. A returning staff member is handled by reactivate_user rather
    than by creating a duplicate name.
    """
    query = db.query(User).filter(func.lower(User.name) == func.lower(name))
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.first() is not None


def create_user(
    db: Session,
    name: str,
    pin: str,
    can_cancel: bool = False,
    can_discount: bool = False,
    can_manage_settings: bool = False,
    is_owner: bool = False,
) -> User:
    """
    Create a new user account.

    BOOTSTRAP RULE: If the users table is empty, the first user is created
    as an Owner (is_owner=True) with all permission flags set to True, regardless
    of what was passed. Owners always have full access.

    Args:
        db: database session
        name: user name (required, must be unique case-insensitively)
        pin: 4-digit PIN (exactly 4 digits)
        can_cancel: allow order cancellations (default False)
        can_discount: allow manual discounts (default False)
        can_manage_settings: allow settings changes (default False)
        is_owner: owner status (default False); if True, all permission flags
                  are also set to True

    Returns:
        The newly created User

    Raises:
        InvalidPINError: if PIN is not exactly 4 digits
        DuplicateNameError: if name already exists (case-insensitive)
    """
    # Validate PIN: exactly 4 digits
    if not (isinstance(pin, str) and pin.isdigit() and len(pin) == 4):
        raise InvalidPINError("PIN must be exactly 4 digits.")

    # Validate name: non-empty (after strip)
    name = name.strip()
    if not name:
        raise ValueError("Name cannot be empty.")

    # Check for duplicate name (case-insensitive)
    if _name_exists_case_insensitive(db, name):
        raise DuplicateNameError(f"A user named '{name}' already exists.")

    # Hash the PIN
    hashed_pin = _hash_pin(pin)

    # Bootstrap: if users table is empty, first user is owner with all permissions
    if db.query(User).count() == 0:
        is_owner = True
        can_cancel = True
        can_discount = True
        can_manage_settings = True
    # Owners always have full permissions
    elif is_owner:
        can_cancel = True
        can_discount = True
        can_manage_settings = True

    # Create user
    user = User(
        name=name,
        pin=hashed_pin,
        can_cancel=can_cancel,
        can_discount=can_discount,
        can_manage_settings=can_manage_settings,
        is_active=True,
        is_owner=is_owner,
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(db: Session, name: str, pin: str) -> tuple[str, User]:
    """
    Authenticate a user and create a session.

    Looks up the user by name (case-insensitive), verifies the PIN with
    bcrypt, and creates a session row with a token. The session expires
    after 90 days (safety net only; no UX timeout).

    Args:
        db: database session
        name: user name
        pin: PIN to verify

    Returns:
        Tuple of (session_token, user)

    Raises:
        AuthenticationFailedError: if name not found, user inactive, or PIN mismatch
    """
    # Find user by name (case-insensitive), active only
    user = db.query(User).filter(
        func.lower(User.name) == func.lower(name),
        User.is_active == True
    ).first()

    if not user:
        # Do NOT reveal whether the name or PIN was wrong
        raise AuthenticationFailedError("Login failed. Check name and PIN.")

    # Verify PIN
    if not _verify_pin(pin, user.pin):
        raise AuthenticationFailedError("Login failed. Check name and PIN.")

    # Create session row
    token = secrets.token_urlsafe(32)  # 43 chars, fits String(64)
    now = datetime.utcnow()
    expires_at = now + timedelta(days=90)

    session = UserSession(
        user_id=user.id,
        token=token,
        created_at=now,
        expires_at=expires_at,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return token, user


def logout(db: Session, token: str) -> None:
    """
    Invalidate a session (delete the row).

    An already-absent token is not an error; this is idempotent.

    Args:
        db: database session
        token: session token to invalidate
    """
    session = db.query(UserSession).filter(UserSession.token == token).first()
    if session:
        db.delete(session)
        db.commit()


def get_current_user(db: Session, token: str) -> User:
    """
    Retrieve the current user from a session token.

    Validates that the session exists and has not expired. Deletes
    expired sessions immediately. Rejects inactive users.

    Args:
        db: database session
        token: session token

    Returns:
        The User associated with the token

    Raises:
        AuthenticationFailedError: if token missing, expired, or user inactive
    """
    session = db.query(UserSession).filter(UserSession.token == token).first()

    if not session:
        raise AuthenticationFailedError("Session not found.")

    # Check expiry (safety net)
    if session.expires_at < datetime.utcnow():
        db.delete(session)
        db.commit()
        raise AuthenticationFailedError("Session expired.")

    # Get user
    user = db.get(User, session.user_id)
    if not user:
        raise AuthenticationFailedError("User not found.")

    # Reject if inactive
    if not user.is_active:
        raise AuthenticationFailedError("User is inactive.")

    return user


def list_users(db: Session) -> list[dict]:
    """
    List all users (active first, sorted by name).

    Returns user details WITHOUT the PIN hash.

    Args:
        db: database session

    Returns:
        List of dicts: {id, name, can_cancel, can_discount, can_manage_settings,
                        is_active, is_owner, created_at}
    """
    users = db.query(User).order_by(
        User.is_active.desc(),  # Active first (True > False)
        User.name
    ).all()

    result = []
    for user in users:
        result.append({
            'id': user.id,
            'name': user.name,
            'can_cancel': user.can_cancel,
            'can_discount': user.can_discount,
            'can_manage_settings': user.can_manage_settings,
            'is_active': user.is_active,
            'is_owner': user.is_owner,
            'created_at': user.created_at,
        })
    return result


def update_user_permissions(
    db: Session,
    user_id: int,
    can_cancel: bool | None = None,
    can_discount: bool | None = None,
    can_manage_settings: bool | None = None,
) -> User:
    """
    Update staff permissions for a user.

    Owner permissions (is_owner) cannot be changed via this function.

    Args:
        db: database session
        user_id: user to update
        can_cancel: new value for can_cancel (optional)
        can_discount: new value for can_discount (optional)
        can_manage_settings: new value for can_manage_settings (optional)

    Returns:
        Updated User

    Raises:
        UserNotFoundError: if user not found
    """
    user = db.get(User, user_id)
    if not user:
        raise UserNotFoundError(f"User {user_id} not found.")

    if can_cancel is not None:
        user.can_cancel = can_cancel
    if can_discount is not None:
        user.can_discount = can_discount
    if can_manage_settings is not None:
        user.can_manage_settings = can_manage_settings

    db.commit()
    db.refresh(user)
    return user


def deactivate_user(db: Session, user_id: int) -> User:
    """
    Deactivate a user (soft delete, never hard-delete).

    Sets is_active=False so past order attribution stays readable.
    Refuses to deactivate the last active Owner (safety check).
    Automatically deletes all sessions for that user so old tokens stop working.

    Args:
        db: database session
        user_id: user to deactivate

    Returns:
        Updated User

    Raises:
        UserNotFoundError: if user not found
        CannotDeactivateLastOwnerError: if this is the last active owner
    """
    user = db.get(User, user_id)
    if not user:
        raise UserNotFoundError(f"User {user_id} not found.")

    # Check if this is an owner and the last active owner
    if user.is_owner and user.is_active:
        active_owner_count = db.query(User).filter(
            User.is_owner == True,
            User.is_active == True
        ).count()
        if active_owner_count == 1:
            raise CannotDeactivateLastOwnerError(
                "Cannot deactivate the last active owner."
            )

    # Deactivate
    user.is_active = False

    # Delete all sessions for this user (invalidate old tokens)
    db.query(UserSession).filter(UserSession.user_id == user_id).delete()

    db.commit()
    db.refresh(user)
    return user


def reactivate_user(db: Session, user_id: int) -> User:
    """
    Reactivate a user (set is_active=True).

    If the user is already active, this is not an error — just return the user.
    Does not create any session; the user logs in normally afterwards.

    Args:
        db: database session
        user_id: user to reactivate

    Returns:
        Updated User

    Raises:
        UserNotFoundError: if user not found
    """
    user = db.get(User, user_id)
    if not user:
        raise UserNotFoundError(f"User {user_id} not found.")

    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


def reset_pin(db: Session, user_id: int, new_pin: str) -> User:
    """
    Reset a user's PIN and invalidate all their sessions.

    All old session tokens become invalid immediately (their rows are deleted).

    Args:
        db: database session
        user_id: user whose PIN to reset
        new_pin: new 4-digit PIN

    Returns:
        Updated User

    Raises:
        UserNotFoundError: if user not found
        InvalidPINError: if new_pin is not exactly 4 digits
    """
    # Validate PIN: exactly 4 digits
    if not (isinstance(new_pin, str) and new_pin.isdigit() and len(new_pin) == 4):
        raise InvalidPINError("PIN must be exactly 4 digits.")

    user = db.get(User, user_id)
    if not user:
        raise UserNotFoundError(f"User {user_id} not found.")

    # Hash and update PIN
    hashed_pin = _hash_pin(new_pin)
    user.pin = hashed_pin

    # Delete all sessions for this user (invalidate old tokens)
    db.query(UserSession).filter(UserSession.user_id == user_id).delete()

    db.commit()
    db.refresh(user)
    return user
