from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine
from analyze import analyze_pending
from ingest import ingest
from models import Category, Email, TrackedSender

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


class CategoryIn(BaseModel):
    name: str
    description: str = ""


class CategoryOut(CategoryIn):
    id: int
    email_count: int = 0

    class Config:
        from_attributes = True


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
    sender_id: Optional[int]
    from_name: Optional[str]
    from_address: Optional[str]
    subject: Optional[str]
    received_at: Optional[datetime]
    category: Optional[str]
    summary: Optional[str]
    classification: Optional[str]

    class Config:
        from_attributes = True


@app.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    # Counts only important emails; unanalyzed ones count too so nothing slips by.
    important = or_(Email.classification.is_(None), Email.classification != "promo")
    counts = dict(
        db.query(Email.category, func.count(Email.id)).filter(important).group_by(Email.category).all()
    )
    categories = db.query(Category).order_by(Category.id).all()
    return [
        CategoryOut(id=c.id, name=c.name, description=c.description or "", email_count=counts.get(c.name, 0))
        for c in categories
    ]


@app.post("/categories", response_model=CategoryOut)
def create_category(category: CategoryIn, db: Session = Depends(get_db)):
    name = category.name.strip().lower()
    if db.query(Category).filter(Category.name == name).first():
        raise HTTPException(status_code=400, detail="Category already exists")
    db_category = Category(name=name, description=category.description.strip())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


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
def list_emails(
    category: Optional[str] = None, include_promos: bool = False, db: Session = Depends(get_db)
):
    query = db.query(Email)
    if category:
        query = query.filter(Email.category == category)
    if not include_promos:
        query = query.filter(or_(Email.classification.is_(None), Email.classification != "promo"))
    return query.order_by(Email.received_at.desc()).all()


# Plain `def` so FastAPI runs this in a worker thread — Gmail calls are blocking.
@app.post("/refresh")
def refresh_emails():
    try:
        result = ingest()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gmail refresh failed: {exc}")
    # New emails get analyzed by Claude when an API key is configured.
    result["analysis"] = analyze_pending()
    return result
