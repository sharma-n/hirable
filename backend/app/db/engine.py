from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_DATA_DIR = Path("app/data")
_DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_URL = f"sqlite:///{_DATA_DIR / 'hirable.db'}"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
