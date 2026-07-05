from sqlalchemy import text

from app.db.base import Base
from app.db.engine import engine
import app.db.models  # noqa: F401 — registers all models on Base.metadata


def run_migrations() -> None:
    Base.metadata.create_all(bind=engine)
    _add_application_event_actor_column()


def _add_application_event_actor_column() -> None:
    """M8: ``application_events.actor`` is a new column on a pre-existing
    table — ``create_all()`` never alters existing tables, so a dev DB
    created before M8 needs this patched in by hand (no Alembic in this
    project). No-op on a fresh DB, where the column already exists."""
    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(application_events)"))}
        if "actor" not in cols:
            conn.execute(text("ALTER TABLE application_events ADD COLUMN actor VARCHAR DEFAULT 'user'"))
            conn.commit()
