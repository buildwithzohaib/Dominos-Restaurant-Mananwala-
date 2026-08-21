"""
Authentication API routes (Stage 7).

Endpoints:
  GET    /auth/bootstrap-status   - Check if system needs initial setup
  POST   /auth/login              - Authenticate and create session
  POST   /auth/logout             - Invalidate session
  GET    /auth/me                 - Get current user from token
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import User
from app.schemas.schemas import LoginIn, LoginOut, UserOut, BootstrapStatusOut
from app.services import user_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_current_user_dep(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to extract and validate the current user from the Authorization header.

    Expected header format: Authorization: Bearer <token>

    Raises:
        HTTPException(401): if header is missing, malformed, or token is invalid
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = parts[1]

    try:
        user = user_service.get_current_user(db=db, token=token)
        return user
    except user_service.AuthenticationFailedError as e:
        raise HTTPException(status_code=401, detail=str(e))


def require_permission(attr_name: str):
    """
    Dependency factory to require a specific permission or is_owner status.

    Args:
        attr_name: The boolean attribute name to check (e.g., "can_cancel", "can_discount")

    Returns a dependency that resolves the current user and verifies either:
        - user.is_owner is True, OR
        - getattr(user, attr_name) is True

    Raises:
        HTTPException(403): if neither condition is met
    """
    async def _require_permission(current_user: User = Depends(get_current_user_dep)) -> User:
        if current_user.is_owner or getattr(current_user, attr_name, False):
            return current_user
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
    return _require_permission


@router.get("/bootstrap-status", response_model=BootstrapStatusOut)
def bootstrap_status(db: Session = Depends(get_db)):
    """
    Check if the system needs bootstrap (first owner creation).

    No authentication required — frontend calls this before showing login screen.
    """
    user_count = db.query(User).count()
    return BootstrapStatusOut(needs_bootstrap=(user_count == 0))


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    """
    Authenticate a user and create a session.

    No authentication required — anyone can attempt login.

    Returns:
        LoginOut with session token and user details

    Raises:
        HTTPException(401): if name not found, user inactive, or PIN mismatch
    """
    try:
        token, user = user_service.login(db=db, name=payload.name, pin=payload.pin)
        return LoginOut(token=token, user=user)
    except user_service.AuthenticationFailedError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except user_service.InvalidPINError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout", status_code=204)
def logout(authorization: str | None = Header(None), db: Session = Depends(get_db)):
    """
    Invalidate a session (logout).

    Reads token from Authorization header. Always succeeds, even if token is
    unknown (idempotent).

    Returns:
        204 No Content
    """
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            user_service.logout(db=db, token=token)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user_dep)):
    """
    Get the current user from the session token.

    Requires:
        Authorization: Bearer <token> header
    """
    return current_user
