from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.models import Base

engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db():
    """create tables if they don't exist (alembic handles migrations in prod)"""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
