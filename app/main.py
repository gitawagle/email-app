from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine
from models import Email, TrackedSender

Base.metadata.create_all(engine)

app = FastAPI()

# Allows the React dev server (different port) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TrackedSenderIn(BaseModel):
    email_address: str
    category: str
    is_cautious: bool = False


class TrackedSenderOut(TrackedSenderIn):
    id: int

    class Config:
        from_attributes = True


class EmailOut(BaseModel):
    id: int
    sender_id: int
    subject: Optional[str]
    received_at: Optional[datetime]
    summary: Optional[str]
    classification: Optional[str]

    class Config:
        from_attributes = True


@app.post("/senders", response_model=TrackedSenderOut)
def create_sender(sender: TrackedSenderIn, db: Session = Depends(get_db)):
    existing = (
        db.query(TrackedSender)
        .filter(TrackedSender.email_address == sender.email_address)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Sender already tracked")

    db_sender = TrackedSender(**sender.model_dump())
    db.add(db_sender)
    db.commit()
    db.refresh(db_sender)
    return db_sender


@app.get("/senders", response_model=list[TrackedSenderOut])
def list_senders(db: Session = Depends(get_db)):
    return db.query(TrackedSender).all()


@app.patch("/senders/{sender_id}", response_model=TrackedSenderOut)
def update_sender(sender_id: int, sender: TrackedSenderIn, db: Session = Depends(get_db)):
    db_sender = db.query(TrackedSender).filter(TrackedSender.id == sender_id).first()
    if not db_sender:
        raise HTTPException(status_code=404, detail="Sender not found")

    db_sender.email_address = sender.email_address
    db_sender.category = sender.category
    db_sender.is_cautious = sender.is_cautious
    db.commit()
    db.refresh(db_sender)
    return db_sender


@app.delete("/senders/{sender_id}")
def delete_sender(sender_id: int, db: Session = Depends(get_db)):
    db_sender = db.query(TrackedSender).filter(TrackedSender.id == sender_id).first()
    if not db_sender:
        raise HTTPException(status_code=404, detail="Sender not found")

    db.delete(db_sender)
    db.commit()
    return {"ok": True}


@app.get("/emails", response_model=list[EmailOut])
def list_emails(category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Email)
    if category:
        query = query.join(TrackedSender).filter(TrackedSender.category == category)
    return query.order_by(Email.received_at.desc()).all()
