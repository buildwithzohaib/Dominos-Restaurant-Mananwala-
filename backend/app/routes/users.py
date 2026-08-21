"""
User management API routes (Stage 7).

Endpoints:
  POST   /api/users                          - Create user (bootstrap + Owner-only)
  GET    /api/users                          - List all users (Owner-only)
  PATCH  /api/users/{user_id}/permissions   - Update permissions (Owner-only)
  POST   /api/users/{user_id}/deactivate    - Deactivate user (Owner-only)
  POST   /api/users/{user_id}/reactivate    - Reactivate user (Owner-only)
  POST   /api/users/{user_id}/reset-pin     - Reset PIN (Owner-only)
"""

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Header
from app.database import get_db
from app.models.models import User
from app.routes.auth import get_current_user_dep
from app.schemas.schemas import (
    UserCreateIn,
    UserPermissionsIn,
    PinResetIn,
    UserOut,
)
from app.services import user_service

router = APIRouter(prefix="/api/users", tags=["users"])


def require_owner(current_user: User = Depends(get_current_user_dep)) -> User:
    """
    Dependency to ensure the current user is an Owner.

    Raises:
        HTTPException(403): if user is not an owner
    """
    if not current_user.is_owner:
        raise HTTPException(status_code=403, detail="Owner access required")
    return current_user


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreateIn,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """
    Create a new user.

    BOOTSTRAP EXCEPTION: if the users table is empty, this endpoint works
    WITHOUT authentication and creates the first Owner. If the table is not
    empty, it requires an Owner.

    Args:
        payload: UserCreateIn with name, pin, and optional permission flags

    Returns:
        UserOut with the created user

    Raises:
        HTTPException(401): if not authenticated when Owner access required
        HTTPException(403): if authenticated but not an Owner, and table is not empty
        HTTPException(400): if invalid PIN, duplicate name, etc.
    """
    # Check if bootstrap is needed
    user_count = db.query(User).count()

    if user_count > 0:
        # Table not empty: require an owner
        current_user = get_current_user_dep(authorization=authorization, db=db)
        if not current_user.is_owner:
            raise HTTPException(status_code=403, detail="Owner access required")

    # Create the user
    try:
        user = user_service.create_user(
            db=db,
            name=payload.name,
            pin=payload.pin,
            can_cancel=payload.can_cancel,
            can_discount=payload.can_discount,
            can_manage_settings=payload.can_manage_settings,
            is_owner=payload.is_owner,
        )
        return user
    except user_service.AuthenticationFailedError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except user_service.DuplicateNameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except user_service.InvalidPINError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), owner: User = Depends(require_owner)):
    """
    List all users (active first, then by name).

    Requires:
        Owner access (valid Authorization header with Owner user)

    Returns:
        List of UserOut (never includes PIN hashes)
    """
    users_list = user_service.list_users(db=db)
    # Convert dicts to UserOut objects
    return [UserOut(**user_dict) for user_dict in users_list]


@router.patch("/{user_id}/permissions", response_model=UserOut)
def update_permissions(
    user_id: int,
    payload: UserPermissionsIn,
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
):
    """
    Update user permissions (Owner-only).

    Does not change owner status (is_owner cannot be modified here).

    Args:
        user_id: user to update
        payload: UserPermissionsIn with optional permission flags

    Returns:
        Updated UserOut

    Raises:
        HTTPException(403): if not an owner
        HTTPException(404): if user not found
        HTTPException(400): for other errors
    """
    try:
        user = user_service.update_user_permissions(
            db=db,
            user_id=user_id,
            can_cancel=payload.can_cancel,
            can_discount=payload.can_discount,
            can_manage_settings=payload.can_manage_settings,
        )
        return user
    except user_service.AuthenticationFailedError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except user_service.UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
):
    """
    Deactivate a user (soft delete, Owner-only).

    Deactivated users cannot log in. All their sessions are invalidated.

    Args:
        user_id: user to deactivate

    Returns:
        Updated UserOut

    Raises:
        HTTPException(403): if not an owner
        HTTPException(400): if last active owner
        HTTPException(404): if user not found
    """
    try:
        user = user_service.deactivate_user(db=db, user_id=user_id)
        return user
    except user_service.AuthenticationFailedError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except user_service.CannotDeactivateLastOwnerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except user_service.UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{user_id}/reactivate", response_model=UserOut)
def reactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
):
    """
    Reactivate a deactivated user (Owner-only).

    Does not create a session; the user logs in normally afterwards.

    Args:
        user_id: user to reactivate

    Returns:
        Updated UserOut

    Raises:
        HTTPException(403): if not an owner
        HTTPException(404): if user not found
    """
    try:
        user = user_service.reactivate_user(db=db, user_id=user_id)
        return user
    except user_service.AuthenticationFailedError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except user_service.UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{user_id}/reset-pin", response_model=UserOut)
def reset_pin(
    user_id: int,
    payload: PinResetIn,
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
):
    """
    Reset a user's PIN (Owner-only).

    The old PIN becomes invalid. All existing sessions for that user are
    invalidated (they cannot use old tokens).

    Args:
        user_id: user whose PIN to reset
        payload: PinResetIn with new_pin (4 digits)

    Returns:
        Updated UserOut

    Raises:
        HTTPException(403): if not an owner
        HTTPException(400): if invalid PIN
        HTTPException(404): if user not found
    """
    try:
        user = user_service.reset_pin(db=db, user_id=user_id, new_pin=payload.new_pin)
        return user
    except user_service.AuthenticationFailedError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except user_service.InvalidPINError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except user_service.UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
