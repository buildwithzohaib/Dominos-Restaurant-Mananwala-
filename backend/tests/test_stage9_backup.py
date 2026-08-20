"""Tests for Stage 9 Database Backup & Restore (backup_service module)."""
import gc
import os
import shutil
import tempfile
import time
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session, declarative_base

from app.services.backup_service import (
    create_backup,
    cleanup_old_backups,
    get_backup_dir,
    get_recent_backup_path,
    restore_database,
)

Base = declarative_base()


class DummyModel(Base):
    """Minimal test model for verification."""
    __tablename__ = "dummy"
    id = Column(Integer, primary_key=True)
    value = Column(String(50))


@pytest.fixture(scope="function")
def temp_db_and_backup():
    """Create a temporary SQLite database and backup directory for testing.

    Yields:
        dict with keys:
        - db_path: absolute path to temp database file
        - backup_dir: absolute path to temp backups directory
        - engine: SQLAlchemy engine
        - session: SQLAlchemy session
    """
    # Create temp directory for database
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    # Create temp directory for backups
    backup_dir = tempfile.mkdtemp()

    try:
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        # Seed with dummy data
        dummy = DummyModel(id=1, value="test_data")
        session.add(dummy)
        session.commit()

        yield {
            "db_path": db_path,
            "backup_dir": backup_dir,
            "engine": engine,
            "session": session,
        }

        session.close()
        engine.dispose()

    finally:
        gc.collect()
        time.sleep(0.1)

        # Cleanup: try multiple times on Windows
        for _ in range(5):
            try:
                if os.path.exists(db_path):
                    os.remove(db_path)
                if os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir)
                break
            except OSError:
                time.sleep(0.1)


class TestCreateBackup:
    """Tests for create_backup() function."""

    def test_create_backup_produces_correctly_named_file(self, temp_db_and_backup):
        """Backup file is named pos_YYYY-MM-DD.db."""
        db_path = temp_db_and_backup["db_path"]
        backup_dir = temp_db_and_backup["backup_dir"]

        created, backup_path = create_backup(db_path, backup_dir)

        assert created is True
        today = date.today().isoformat()
        expected_filename = f"pos_{today}.db"
        assert os.path.basename(backup_path) == expected_filename
        assert os.path.exists(backup_path)

    def test_running_backup_twice_same_day_only_creates_one_file(self, temp_db_and_backup):
        """Second backup run same day returns False and doesn't create new file."""
        db_path = temp_db_and_backup["db_path"]
        backup_dir = temp_db_and_backup["backup_dir"]

        # First run
        created1, path1 = create_backup(db_path, backup_dir)
        assert created1 is True

        # Second run same day
        created2, path2 = create_backup(db_path, backup_dir)
        assert created2 is False
        assert path1 == path2

        # Verify only one backup file exists
        backup_files = [f for f in os.listdir(backup_dir) if f.startswith("pos_") and f.endswith(".db")]
        assert len(backup_files) == 1

    def test_backup_file_is_copy_of_database(self, temp_db_and_backup):
        """Backup file contains the same data as the original database."""
        db_path = temp_db_and_backup["db_path"]
        backup_dir = temp_db_and_backup["backup_dir"]
        session = temp_db_and_backup["session"]

        # Create backup
        created, backup_path = create_backup(db_path, backup_dir)
        assert created is True

        # Read backup file as a new database
        backup_engine = create_engine(f"sqlite:///{backup_path}")
        BackupSession = sessionmaker(bind=backup_engine)
        backup_session = BackupSession()

        # Verify data exists in backup
        backup_data = backup_session.query(DummyModel).filter_by(id=1).first()
        assert backup_data is not None
        assert backup_data.value == "test_data"

        backup_session.close()
        backup_engine.dispose()

    def test_create_backup_creates_backups_dir_if_missing(self):
        """If backups/ doesn't exist, create_backup creates it."""
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        backup_dir = os.path.join(tempfile.gettempdir(), "nonexistent_backup_dir_test")

        try:
            assert not os.path.exists(backup_dir)

            created, backup_path = create_backup(db_path, backup_dir)

            assert created is True
            assert os.path.exists(backup_dir)
            assert os.path.exists(backup_path)
        finally:
            for _ in range(5):
                try:
                    if os.path.exists(db_path):
                        os.remove(db_path)
                    if os.path.exists(backup_dir):
                        shutil.rmtree(backup_dir)
                    break
                except OSError:
                    time.sleep(0.1)


class TestCleanupOldBackups:
    """Tests for cleanup_old_backups() function."""

    def test_cleanup_removes_backups_older_than_30_days(self, temp_db_and_backup):
        """Backups older than 30 days are deleted."""
        backup_dir = temp_db_and_backup["backup_dir"]

        # Create fake old backup file (31 days ago)
        old_date = (date.today() - timedelta(days=31)).isoformat()
        old_backup = os.path.join(backup_dir, f"pos_{old_date}.db")
        with open(old_backup, "w") as f:
            f.write("old_backup_content")

        # Create fake recent backup file (10 days ago)
        recent_date = (date.today() - timedelta(days=10)).isoformat()
        recent_backup = os.path.join(backup_dir, f"pos_{recent_date}.db")
        with open(recent_backup, "w") as f:
            f.write("recent_backup_content")

        # Run cleanup
        deleted = cleanup_old_backups(backup_dir, keep_days=30)

        # Old backup should be deleted, recent kept
        assert old_backup in deleted
        assert not os.path.exists(old_backup)
        assert os.path.exists(recent_backup)

    def test_cleanup_keeps_recent_backups(self, temp_db_and_backup):
        """Backups within 30 days are kept."""
        backup_dir = temp_db_and_backup["backup_dir"]

        # Create backup files at various dates
        for days_ago in [1, 5, 15, 29, 30]:
            backup_date = (date.today() - timedelta(days=days_ago)).isoformat()
            backup_file = os.path.join(backup_dir, f"pos_{backup_date}.db")
            with open(backup_file, "w") as f:
                f.write(f"backup_{days_ago}_days_ago")

        deleted = cleanup_old_backups(backup_dir, keep_days=30)

        # Nothing older than 30 days should be deleted
        assert len(deleted) == 0

        # All files should still exist
        for days_ago in [1, 5, 15, 29, 30]:
            backup_date = (date.today() - timedelta(days=days_ago)).isoformat()
            backup_file = os.path.join(backup_dir, f"pos_{backup_date}.db")
            assert os.path.exists(backup_file)

    def test_cleanup_never_deletes_safety_backups(self, temp_db_and_backup):
        """Files named pos_before_restore_* are never deleted."""
        backup_dir = temp_db_and_backup["backup_dir"]

        # Create a safety backup file (won't be deleted even if very old)
        safety_backup = os.path.join(backup_dir, "pos_before_restore_2020-01-01T120000.db")
        with open(safety_backup, "w") as f:
            f.write("safety_backup_content")

        # Run cleanup with very small keep_days
        deleted = cleanup_old_backups(backup_dir, keep_days=0)

        # Safety backup should NOT be in deleted list
        assert safety_backup not in deleted
        assert os.path.exists(safety_backup)

    def test_cleanup_handles_missing_backups_dir(self):
        """Cleanup doesn't crash if backups/ doesn't exist."""
        backup_dir = os.path.join(tempfile.gettempdir(), "nonexistent_backup_cleanup_test")
        assert not os.path.exists(backup_dir)

        # Should not raise, should return empty list
        deleted = cleanup_old_backups(backup_dir, keep_days=30)
        assert deleted == []

    def test_cleanup_handles_empty_backups_dir(self, temp_db_and_backup):
        """Cleanup doesn't crash if backups/ is empty."""
        backup_dir = temp_db_and_backup["backup_dir"]
        assert os.path.isdir(backup_dir)

        # Should not raise, should return empty list
        deleted = cleanup_old_backups(backup_dir, keep_days=30)
        assert deleted == []


class TestGetRecentBackup:
    """Tests for get_recent_backup_path() function."""

    def test_get_recent_backup_returns_latest_file(self, temp_db_and_backup):
        """Most recent backup file is returned."""
        backup_dir = temp_db_and_backup["backup_dir"]

        # Create multiple backup files
        for days_ago in [10, 5, 1]:
            backup_date = (date.today() - timedelta(days=days_ago)).isoformat()
            backup_file = os.path.join(backup_dir, f"pos_{backup_date}.db")
            with open(backup_file, "w") as f:
                f.write(f"backup_{days_ago}_days_ago")

        recent = get_recent_backup_path(backup_dir)

        # Should return the 1-day-old backup (most recent)
        assert recent is not None
        today_minus_1 = (date.today() - timedelta(days=1)).isoformat()
        assert os.path.basename(recent) == f"pos_{today_minus_1}.db"

    def test_get_recent_backup_ignores_safety_backups(self, temp_db_and_backup):
        """Safety backup files are not considered recent."""
        backup_dir = temp_db_and_backup["backup_dir"]

        # Create a regular backup
        regular_backup_date = (date.today() - timedelta(days=5)).isoformat()
        regular_backup = os.path.join(backup_dir, f"pos_{regular_backup_date}.db")
        with open(regular_backup, "w") as f:
            f.write("regular_backup")

        # Create a safety backup (newer by filename)
        safety_backup = os.path.join(backup_dir, "pos_before_restore_2026-08-20T143022.db")
        with open(safety_backup, "w") as f:
            f.write("safety_backup")

        recent = get_recent_backup_path(backup_dir)

        # Should return the regular backup, not the safety backup
        assert recent is not None
        assert "before_restore" not in os.path.basename(recent)

    def test_get_recent_backup_returns_none_if_no_backups(self, temp_db_and_backup):
        """Returns None if no backup files exist."""
        backup_dir = temp_db_and_backup["backup_dir"]
        recent = get_recent_backup_path(backup_dir)
        assert recent is None

    def test_get_recent_backup_returns_none_if_dir_missing(self):
        """Returns None if backups/ doesn't exist."""
        backup_dir = os.path.join(tempfile.gettempdir(), "nonexistent_backup_recent_test")
        assert not os.path.exists(backup_dir)
        recent = get_recent_backup_path(backup_dir)
        assert recent is None


class TestRestoreDatabase:
    """Tests for restore_database() function."""

    def test_restore_creates_safety_backup_before_swap(self, temp_db_and_backup):
        """Pre-restore safety backup is created before database swap."""
        db_path = temp_db_and_backup["db_path"]
        backup_dir = temp_db_and_backup["backup_dir"]
        engine = temp_db_and_backup["engine"]
        session = temp_db_and_backup["session"]

        # Create a backup to restore from
        create_backup(db_path, backup_dir)

        # Modify the current database (change value)
        dummy = session.query(DummyModel).filter_by(id=1).first()
        dummy.value = "modified_data"
        session.commit()

        # Restore
        response = restore_database(db_path, backup_dir, engine)

        assert response["success"] is True
        assert response["safety_backup"] is not None

        # Verify safety backup file exists
        safety_backup_path = os.path.join(backup_dir, response["safety_backup"])
        assert os.path.exists(safety_backup_path)

        # Verify safety backup contains the modified data
        backup_engine = create_engine(f"sqlite:///{safety_backup_path}")
        BackupSession = sessionmaker(bind=backup_engine)
        backup_session = BackupSession()
        backup_data = backup_session.query(DummyModel).filter_by(id=1).first()
        assert backup_data.value == "modified_data"
        backup_session.close()
        backup_engine.dispose()

    def test_restore_replaces_database_file(self, temp_db_and_backup):
        """Database file is overwritten with backup content."""
        db_path = temp_db_and_backup["db_path"]
        backup_dir = temp_db_and_backup["backup_dir"]
        engine = temp_db_and_backup["engine"]
        session = temp_db_and_backup["session"]

        # Create backup
        create_backup(db_path, backup_dir)

        # Modify database
        dummy = session.query(DummyModel).filter_by(id=1).first()
        original_value = dummy.value
        dummy.value = "modified_data"
        session.commit()

        # Restore
        response = restore_database(db_path, backup_dir, engine)
        assert response["success"] is True

        # Reopen the database and verify data is restored
        restored_engine = create_engine(f"sqlite:///{db_path}")
        RestoredSession = sessionmaker(bind=restored_engine)
        restored_session = RestoredSession()
        restored_data = restored_session.query(DummyModel).filter_by(id=1).first()

        assert restored_data.value == original_value  # Should be "test_data", not "modified_data"

        restored_session.close()
        restored_engine.dispose()

    def test_restore_response_indicates_restart_required(self, temp_db_and_backup):
        """Response has restart_required: true."""
        db_path = temp_db_and_backup["db_path"]
        backup_dir = temp_db_and_backup["backup_dir"]
        engine = temp_db_and_backup["engine"]

        # Create backup
        create_backup(db_path, backup_dir)

        # Restore
        response = restore_database(db_path, backup_dir, engine)

        assert response["success"] is True
        assert response["restart_required"] is True
        assert "restart" in response["message"].lower()

    def test_restore_returns_error_if_no_backup_found(self, temp_db_and_backup):
        """Response indicates failure if no backup exists."""
        db_path = temp_db_and_backup["db_path"]
        backup_dir = temp_db_and_backup["backup_dir"]
        engine = temp_db_and_backup["engine"]

        # Don't create any backup
        response = restore_database(db_path, backup_dir, engine)

        assert response["success"] is False
        assert "No backup" in response["error"]
        assert response["restart_required"] is False

    def test_restore_includes_backup_date_in_response(self, temp_db_and_backup):
        """Response includes the date of the restored backup."""
        db_path = temp_db_and_backup["db_path"]
        backup_dir = temp_db_and_backup["backup_dir"]
        engine = temp_db_and_backup["engine"]

        # Create backup
        create_backup(db_path, backup_dir)

        # Restore
        response = restore_database(db_path, backup_dir, engine)

        assert response["success"] is True
        assert response["backup_date"] is not None
        today = date.today().isoformat()
        assert response["backup_date"] == today
