from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class TrackedSender(Base):
    __tablename__ = "tracked_senders"

    id = Column(Integer, primary_key=True)
    email_address = Column(String, unique=True, nullable=False)
    category = Column(String, nullable=False)  # e.g. "job search", "shopping"
    is_cautious = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    emails = relationship("Email", back_populates="sender")


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True)
    gmail_message_id = Column(String, unique=True, nullable=False)
    sender_id = Column(Integer, ForeignKey("tracked_senders.id"), nullable=False)

    subject = Column(String)
    received_at = Column(DateTime)
    body = Column(Text)  # raw email content pulled from Gmail

    summary = Column(Text, nullable=True)  # filled in by Claude later
    classification = Column(String, nullable=True)  # e.g. "advancement" vs "marketing"

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    sender = relationship("TrackedSender", back_populates="emails")
