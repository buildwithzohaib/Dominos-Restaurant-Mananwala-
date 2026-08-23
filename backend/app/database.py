import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def get_data_dir() -> str:
    """
    Determine the data directory for the application at runtime.

    Priority (first match wins):
    1. POS_DATA_DIR environment variable (if set)
    2. If app is frozen (PyInstaller): %LOCALAPPDATA%\<AppName>
       - AppName read from POS_APP_NAME env var, default "RestaurantPOS"
    3. Development mode (default): backend/ folder (code directory)

    Creates the directory if it does not exist.

    Returns:
        Absolute path to the data directory
    """
    # Check for explicit environment variable override
    if pos_data_dir := os.environ.get("POS_DATA_DIR"):
        os.makedirs(pos_data_dir, exist_ok=True)
        return pos_data_dir

    # Check if running as frozen (PyInstaller) executable
    if getattr(sys, "frozen", False):
        app_name = os.environ.get("POS_APP_NAME", "RestaurantPOS")
        local_app_data = os.path.expandvars("%LOCALAPPDATA%")
        data_dir = os.path.join(local_app_data, app_name)
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    # Development mode: use backend/ folder
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return backend_dir


# Anchor the SQLite file to the backend/ directory regardless of the process's
# current working directory, so `uvicorn app.main:app` and `python seed.py`
# always resolve to the same database file no matter where they're launched from.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Data directory: for development, same as BACKEND_DIR; for production, uses get_data_dir()
DATA_DIR = get_data_dir()
DB_PATH = os.path.join(DATA_DIR, 'pos.db')
DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
