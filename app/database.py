"""
Database configuration and session management.
"""
from sqlmodel import SQLModel, create_engine, Session
from typing import Generator

# SQLite database URL for MVP
DATABASE_URL = "sqlite:///./chronos.db"

# For production, switch to PostgreSQL:
# DATABASE_URL = "postgresql://user:password@localhost/chronos"

engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables():
    """Create database tables."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
