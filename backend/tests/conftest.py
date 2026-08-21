"""
Pytest configuration and shared fixtures for the test suite.

Stage 7: Override get_current_user_dep for route tests that don't need to test
authentication specifically. This allows existing tests to continue passing after
router-level authentication was added.
"""

import pytest
from app.main import app
from app.models.models import User
from app.routes.auth import get_current_user_dep


@pytest.fixture(scope="function", autouse=True)
def override_auth_for_tests():
    """
    Override get_current_user_dep with a fake Owner user for all route tests.

    This allows tests written before authentication was added to continue passing.
    Tests that specifically verify authentication behavior should build their own
    TestClient without this override.
    """
    # Create a fake Owner user in memory (never persisted to database)
    fake_owner = User(
        id=1,
        name="TestOwner",
        pin="",  # Not used in override
        can_cancel=True,
        can_discount=True,
        can_manage_settings=True,
        is_active=True,
        is_owner=True,
    )

    # Set the override
    app.dependency_overrides[get_current_user_dep] = lambda: fake_owner

    yield

    # Clean up after tests complete
    app.dependency_overrides.clear()
