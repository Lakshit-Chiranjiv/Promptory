import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Resolve project root (two levels up from this file: app/ -> root/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "promptvc.db")

# sqlite:///  +  absolute path — three slashes = absolute path convention
DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False — SQLite default blocks multi-thread access; needed for FastAPI
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# autocommit/autoflush=False — explicit transaction control; nothing hits DB until .commit()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base — all ORM models inherit from this so SQLAlchemy tracks them."""
    pass


def get_db():
    """
    FastAPI dependency — opens a DB session before the route runs, closes it after.
    `yield` makes this a generator; finally block guarantees cleanup on error too.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
