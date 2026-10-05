from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)  # e.g. "vox", "online shopping"
    description = Column(Text, default="")  # tells Claude what belongs here


class TrackedSender(Base):
    """A sender pinned to a category - their emails skip Claude's category guess."""

    __tablename__ = "tracked_senders"

    id = Column(Integer, primary_key=True)
    email_address = Column(String, unique=True, nullable=False)
    category = Column(String, nullable=False)
    is_cautious = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    emails = relationship("Email", back_populates="sender")


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True)
    gmail_message_id = Column(String, unique=True, nullable=False)
    sender_id = Column(Integer, ForeignKey("tracked_senders.id"), nullable=True)

    from_name = Column(String)
    from_address = Column(String)
    subject = Column(String)
    received_at = Column(DateTime)
    body = Column(Text)  # plain text (HTML converted) pulled from Gmail

    category = Column(String, nullable=True)  # set by a tracked sender or by Claude
    summary = Column(Text, nullable=True)  # Claude's bullet points, one per line
    classification = Column(String, nullable=True)  # e.g. "action needed", "update", "promo"

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    sender = relationship("TrackedSender", back_populates="emails")
