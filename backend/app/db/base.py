"""SQLAlchemy engine, session factory, and declarative base.

The connection URL comes from ``DATABASE_URL`` (Supabase/Neon). We normalise it
so it always uses the psycopg 3 driver and always requests SSL, since Supabase
rejects non-SSL connections.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import settings


class Base(DeclarativeBase):
    pass


def normalise_url(raw: str) -> str:
    """Force the psycopg3 driver and require SSL.

    Accepts the plain ``postgresql://...`` string Supabase hands out and turns
    it into ``postgresql+psycopg://...?sslmode=require``.
    """
    if not raw:
        raise RuntimeError(
            "DATABASE_URL is not set. Add your Supabase/Neon connection string "
            "to .env before running migrations or the app."
        )
    url = make_url(raw)
    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+psycopg")
    if "sslmode" not in url.query:
        url = url.update_query_dict({"sslmode": "require"}, append=True)
    return url.render_as_string(hide_password=False)


def build_engine(echo: bool = False) -> Engine:
    return create_engine(
        normalise_url(settings.database_url),
        echo=echo,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


engine: Engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Session:
    return SessionLocal()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
