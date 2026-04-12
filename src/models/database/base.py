"""
SQLAlchemy database connection and base model.
Creates engine and session factory from DATABASE_URL.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config.settings import settings

# Validate required environment variables before creating engine
settings.validate_required()

# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    settings.database_url,
    pool_size=5,           # Maintain 5 persistent connections
    max_overflow=10,       # Allow up to 10 extra connections under load
    pool_timeout=30,       # Wait 30s for available connection
    pool_recycle=1800,     # Recycle connections every 30 minutes
    echo=False,            # Set True for SQL query logging
)

# Session factory - call Session() to get a new session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all ORM models
Base = declarative_base()


def get_db_session():
    """
    Context manager for database sessions.
    Automatically commits on success, rolls back on error.

    Usage:
        with get_db_session() as db:
            db.query(Project).all()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
