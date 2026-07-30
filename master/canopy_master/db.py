import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Same override pattern as edge-agent's db.py (CANOPY_DATA_DIR there, this repo's own
# var here) — lets a Docker volume mount this somewhere durable rather than the
# container's own throwaway filesystem.
DATA_DIR = Path(os.environ.get("CANOPY_MASTER_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "master.db"

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass
