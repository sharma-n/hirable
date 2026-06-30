from app.db.base import Base
from app.db.engine import engine
import app.db.models  # noqa: F401 — registers all models on Base.metadata


def run_migrations() -> None:
    Base.metadata.create_all(bind=engine)
