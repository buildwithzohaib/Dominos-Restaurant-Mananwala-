"""CLI entrypoint kept for the `python seed.py` workflow documented in the README.
The actual seed logic lives in app/seed.py so it can also be imported as
`app.seed` at API startup (see app/main.py)."""
from app.seed import seed_data

if __name__ == "__main__":
    seed_data()
