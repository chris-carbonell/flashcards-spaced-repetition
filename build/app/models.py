from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, DateTime, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def utcnow():
    return datetime.now(timezone.utc)


class CardReview(Base):
    """spaced repetition state per card slug"""
    __tablename__ = "card_reviews"

    card_slug = Column(String, primary_key=True)
    ease_factor = Column(Float, default=2.5, nullable=False)
    interval_days = Column(Integer, default=0, nullable=False)
    repetitions = Column(Integer, default=0, nullable=False)
    next_review_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_reviewed_at = Column(DateTime(timezone=True), nullable=True)


class ReviewLog(Base):
    """full history of every review"""
    __tablename__ = "review_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    card_slug = Column(String, nullable=False)
    rating = Column(Integer, nullable=False)  # 0-5 SM-2 scale
    ease_factor_after = Column(Float, nullable=False)
    interval_days_after = Column(Integer, nullable=False)
    reviewed_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    response_seconds = Column(Integer, nullable=True)  # how long they took to answer
