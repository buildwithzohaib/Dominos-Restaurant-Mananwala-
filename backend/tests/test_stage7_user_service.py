"""
User Service Testing Suite (Stage 7)

Comprehensive tests for user creation, authentication, permissions, and session
management. Uses fresh temporary database per test to avoid cross-test contamination.
"""

import pytest
import tempfile
import os
import gc
import time
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.database import Base
from app.models.models import User, UserSession
from app.services import user_service
from app.services.user_service import (
    create_user,
    login,
    logout,
    get_current_user,
    list_users,
    update_user_permissions,
    deactivate_user,
    reactivate_user,
    reset_pin,
    DuplicateNameError,
    InvalidPINError,
    AuthenticationFailedError,
    UserNotFoundError,
    CannotDeactivateLastOwnerError,
)


@pytest.fixture(scope="function")
def engine():
    """Create a fresh temporary SQLite engine for each test."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        test_engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(bind=test_engine)
        yield test_engine
    finally:
        test_engine.raw_connection().close() if hasattr(test_engine.raw_connection(), 'close') else None
        test_engine.dispose()
        gc.collect()
        time.sleep(0.1)
        if os.path.exists(db_path):
            for attempt in range(3):
                try:
                    os.remove(db_path)
                    break
                except OSError:
                    if attempt < 2:
                        gc.collect()
                        time.sleep(0.05)


@pytest.fixture(scope="function")
def db_session(engine):
    """Create a database session for direct access."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    yield db
    db.close()


# ============================================================================
# BOOTSTRAP AND CREATION TESTS
# ============================================================================

class TestUserCreation:
    """User creation and bootstrap tests."""

    def test_first_user_becomes_owner_with_all_permissions(self, db_session):
        """First user in empty table becomes is_owner=True with all permissions True"""
        user = create_user(db_session, name="Ali", pin="1234")

        assert user.is_owner is True
        assert user.can_cancel is True
        assert user.can_discount is True
        assert user.can_manage_settings is True
        assert user.is_active is True

    def test_second_user_not_owner_no_permissions(self, db_session):
        """Second user created with no flags is not an owner, all permissions False"""
        # Create first user (owner)
        create_user(db_session, name="Owner", pin="1111")

        # Create second user
        user = create_user(db_session, name="Staff", pin="2222")

        assert user.is_owner is False
        assert user.can_cancel is False
        assert user.can_discount is False
        assert user.can_manage_settings is False
        assert user.is_active is True

    def test_user_created_with_is_owner_true_gets_all_permissions(self, db_session):
        """User created with is_owner=True gets all three permissions True"""
        # First user (will be owner by bootstrap)
        create_user(db_session, name="Owner1", pin="1111")

        # Second user explicitly marked as owner
        user = create_user(db_session, name="Owner2", pin="2222", is_owner=True)

        assert user.is_owner is True
        assert user.can_cancel is True
        assert user.can_discount is True
        assert user.can_manage_settings is True

    def test_duplicate_name_rejected_case_insensitively(self, db_session):
        """Duplicate name rejected case-insensitively (ali vs Ali)"""
        create_user(db_session, name="ali", pin="1234")

        with pytest.raises(DuplicateNameError) as exc_info:
            create_user(db_session, name="Ali", pin="5678")

        assert "already exists" in str(exc_info.value)

    def test_invalid_pin_three_digits(self, db_session):
        """PIN with 3 digits raises InvalidPINError"""
        with pytest.raises(InvalidPINError):
            create_user(db_session, name="Ali", pin="123")

    def test_invalid_pin_five_digits(self, db_session):
        """PIN with 5 digits raises InvalidPINError"""
        with pytest.raises(InvalidPINError):
            create_user(db_session, name="Ali", pin="12345")

    def test_invalid_pin_non_numeric(self, db_session):
        """PIN with non-numeric characters raises InvalidPINError"""
        with pytest.raises(InvalidPINError):
            create_user(db_session, name="Ali", pin="12ab")

    def test_two_users_different_names_same_pin_succeeds(self, db_session):
        """Two users with different names but same PIN can both be created"""
        user1 = create_user(db_session, name="Ali", pin="1234")
        user2 = create_user(db_session, name="Ahmed", pin="1234")

        assert user1.id != user2.id
        assert user1.name == "Ali"
        assert user2.name == "Ahmed"
        # Both should exist and have different IDs


# ============================================================================
# LOGIN TESTS
# ============================================================================

class TestUserLogin:
    """User login and authentication tests."""

    def test_login_correct_credentials_returns_token_and_user(self, db_session):
        """Login with correct name and PIN returns token and user"""
        created_user = create_user(db_session, name="Ali", pin="1234")

        token, user = login(db_session, name="Ali", pin="1234")

        assert user.id == created_user.id
        assert user.name == "Ali"
        assert len(token) <= 64
        assert len(token) > 0

    def test_login_case_insensitive_on_name(self, db_session):
        """Login is case-insensitive on name (ali vs Ali)"""
        created_user = create_user(db_session, name="Ali", pin="1234")

        token, user = login(db_session, name="ali", pin="1234")

        assert user.id == created_user.id

    def test_login_wrong_pin_raises_auth_error(self, db_session):
        """Login with wrong PIN raises AuthenticationFailedError"""
        create_user(db_session, name="Ali", pin="1234")

        with pytest.raises(AuthenticationFailedError):
            login(db_session, name="Ali", pin="5678")

    def test_login_unknown_name_raises_auth_error(self, db_session):
        """Login with unknown name raises AuthenticationFailedError"""
        with pytest.raises(AuthenticationFailedError):
            login(db_session, name="Unknown", pin="1234")

    def test_login_deactivated_user_raises_auth_error(self, db_session):
        """Login with a deactivated user raises AuthenticationFailedError"""
        # Create an owner first (bootstrap)
        owner = create_user(db_session, name="Owner", pin="1111")
        # Create a staff user
        staff = create_user(db_session, name="Staff", pin="2222")
        # Deactivate the staff user
        deactivate_user(db_session, staff.id)

        with pytest.raises(AuthenticationFailedError):
            login(db_session, name="Staff", pin="2222")


# ============================================================================
# SESSION TESTS
# ============================================================================

class TestUserSessions:
    """User session management tests."""

    def test_get_current_user_valid_token(self, db_session):
        """get_current_user with valid token returns the user"""
        user = create_user(db_session, name="Ali", pin="1234")
        token, _ = login(db_session, name="Ali", pin="1234")

        current_user = get_current_user(db_session, token)

        assert current_user.id == user.id
        assert current_user.name == "Ali"

    def test_get_current_user_unknown_token_raises_error(self, db_session):
        """get_current_user with unknown token raises AuthenticationFailedError"""
        with pytest.raises(AuthenticationFailedError):
            get_current_user(db_session, "invalid_token_xyz")

    def test_get_current_user_expired_session_raises_error_and_deletes_row(self, db_session):
        """Expired session raises error and deletes the session row"""
        user = create_user(db_session, name="Ali", pin="1234")
        token, _ = login(db_session, name="Ali", pin="1234")

        # Find session and make it expired
        session = db_session.query(UserSession).filter(UserSession.token == token).first()
        session.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db_session.commit()

        # Attempt to get current user should fail
        with pytest.raises(AuthenticationFailedError):
            get_current_user(db_session, token)

        # Session row should be deleted
        remaining_sessions = db_session.query(UserSession).filter(UserSession.token == token).count()
        assert remaining_sessions == 0

    def test_logout_deletes_session_token_stops_working(self, db_session):
        """Logout deletes session; token stops working"""
        create_user(db_session, name="Ali", pin="1234")
        token, _ = login(db_session, name="Ali", pin="1234")

        # Verify token works before logout
        user = get_current_user(db_session, token)
        assert user.name == "Ali"

        # Logout
        logout(db_session, token)

        # Token should no longer work
        with pytest.raises(AuthenticationFailedError):
            get_current_user(db_session, token)

    def test_logout_nonexistent_token_no_error(self, db_session):
        """Logout with non-existent token is idempotent (no error)"""
        # Should not raise
        logout(db_session, "nonexistent_token")


# ============================================================================
# PERMISSIONS AND LIFECYCLE TESTS
# ============================================================================

class TestUserPermissions:
    """User permission management tests."""

    def test_update_user_permissions_changes_flags(self, db_session):
        """update_user_permissions changes the three permission flags"""
        # Create an owner first (bootstrap)
        owner = create_user(db_session, name="Owner", pin="1111")
        # Create a staff user (not owner, no permissions)
        staff = create_user(db_session, name="Staff", pin="2222", is_owner=False)
        assert staff.can_cancel is False
        assert staff.can_discount is False
        assert staff.can_manage_settings is False

        # Update permissions
        updated = update_user_permissions(
            db_session,
            staff.id,
            can_cancel=True,
            can_discount=True,
            can_manage_settings=False
        )

        assert updated.can_cancel is True
        assert updated.can_discount is True
        assert updated.can_manage_settings is False


class TestUserDeactivation:
    """User deactivation and reactivation tests."""

    def test_deactivate_only_owner_raises_error(self, db_session):
        """Deactivating the only active owner raises CannotDeactivateLastOwnerError"""
        user = create_user(db_session, name="Owner", pin="1234")
        # user is the only owner (bootstrap rule)

        with pytest.raises(CannotDeactivateLastOwnerError):
            deactivate_user(db_session, user.id)

    def test_deactivate_staff_member_sets_inactive_and_deletes_sessions(self, db_session):
        """Deactivating a staff member sets is_active=False and deletes sessions"""
        owner = create_user(db_session, name="Owner", pin="1111")
        staff = create_user(db_session, name="Staff", pin="2222")

        # Create a session for staff
        token, _ = login(db_session, name="Staff", pin="2222")
        assert get_current_user(db_session, token).id == staff.id

        # Deactivate staff
        deactivate_user(db_session, staff.id)

        # Check is_active
        reloaded = db_session.query(User).filter(User.id == staff.id).first()
        assert reloaded.is_active is False

        # Session should be gone
        with pytest.raises(AuthenticationFailedError):
            get_current_user(db_session, token)

    def test_reactivate_user_makes_login_possible_again(self, db_session):
        """reactivate_user makes a deactivated user able to log in"""
        owner = create_user(db_session, name="Owner", pin="1111")
        user = create_user(db_session, name="Staff", pin="2222")

        # Deactivate
        deactivate_user(db_session, user.id)

        # Should not be able to login
        with pytest.raises(AuthenticationFailedError):
            login(db_session, name="Staff", pin="2222")

        # Reactivate
        reactivate_user(db_session, user.id)

        # Should be able to login now
        token, logged_in_user = login(db_session, name="Staff", pin="2222")
        assert logged_in_user.id == user.id

    def test_deactivate_owner_allowed_when_another_owner_exists(self, db_session):
        """Deactivating an owner is allowed when another active owner exists"""
        # Create the bootstrap owner
        owner1 = create_user(db_session, name="Owner1", pin="1111")
        # Create a second owner
        owner2 = create_user(db_session, name="Owner2", pin="2222", is_owner=True)

        # Should be able to deactivate owner1 since owner2 exists
        deactivate_user(db_session, owner1.id)

        # Verify owner1 is inactive
        reloaded = db_session.query(User).filter(User.id == owner1.id).first()
        assert reloaded.is_active is False

        # owner1 should not be able to login anymore
        with pytest.raises(AuthenticationFailedError):
            login(db_session, name="Owner1", pin="1111")

        # owner2 should still be able to login
        token, logged_in = login(db_session, name="Owner2", pin="2222")
        assert logged_in.id == owner2.id


class TestUserPasswordReset:
    """User PIN reset tests."""

    def test_reset_pin_old_pin_stops_working_new_pin_works(self, db_session):
        """reset_pin: old PIN stops working, new PIN works"""
        user = create_user(db_session, name="Ali", pin="1234")

        # Login with old PIN works
        token, _ = login(db_session, name="Ali", pin="1234")

        # Reset PIN
        reset_pin(db_session, user.id, new_pin="5678")

        # Old PIN should not work
        with pytest.raises(AuthenticationFailedError):
            login(db_session, name="Ali", pin="1234")

        # New PIN should work
        new_token, logged_in = login(db_session, name="Ali", pin="5678")
        assert logged_in.id == user.id

    def test_reset_pin_invalidates_existing_sessions(self, db_session):
        """reset_pin invalidates all existing sessions"""
        user = create_user(db_session, name="Ali", pin="1234")

        # Create multiple sessions
        token1, _ = login(db_session, name="Ali", pin="1234")
        token2, _ = login(db_session, name="Ali", pin="1234")

        # Verify both tokens work
        assert get_current_user(db_session, token1).id == user.id
        assert get_current_user(db_session, token2).id == user.id

        # Reset PIN
        reset_pin(db_session, user.id, new_pin="5678")

        # Both old tokens should be gone
        with pytest.raises(AuthenticationFailedError):
            get_current_user(db_session, token1)
        with pytest.raises(AuthenticationFailedError):
            get_current_user(db_session, token2)


# ============================================================================
# LIST USERS TESTS
# ============================================================================

class TestListUsers:
    """list_users function tests."""

    def test_list_users_never_includes_pin_hash(self, db_session):
        """list_users never includes PIN or PIN hash in output"""
        user1 = create_user(db_session, name="Ali", pin="1234")
        user2 = create_user(db_session, name="Ahmed", pin="5678")

        users = list_users(db_session)

        assert len(users) == 2
        for user_dict in users:
            assert "pin" not in user_dict
            assert user_dict["name"] in ["Ali", "Ahmed"]
            assert user_dict["is_owner"] in [True, False]
            assert "can_cancel" in user_dict
            assert "can_discount" in user_dict
            assert "can_manage_settings" in user_dict
            assert "created_at" in user_dict
