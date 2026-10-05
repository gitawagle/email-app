"""Send unanalyzed emails to Claude for a category, a label, and key bullet points.

Needs ANTHROPIC_API_KEY in the environment or in a .env file at the project root.
"""

import os
from pathlib import Path
from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from database import SessionLocal
from models import Category, Email

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MODEL = "claude-opus-5-5"
MAX_BODY_CHARS = 12000  # newsletters can be huge; the key details are near the top

SYSTEM_PROMPT = """You sort and summarize emails for one person's personal inbox tracker. \
They only want to see emails about something that actually happened to them or needs them.

For each email:
- Pick the single best category from the list provided. Use "other" when none fits.
- Pick a label:
  - "action needed": they must do something, e.g. pay a bill, confirm a sign-in, reply, sign, pick up a package.
  - "update": a real event involving them, e.g. order placed, shipped, delivered, cancelled or refunded; \
receipts; application received or status changed; interview invites; rent or building notices; account changes.
  - "promo": everything else, including sales, newsletters, recommendations, cart reminders, \
job-alert digests, saved-search alerts, social notifications and expired login codes.
- Write 1-4 short bullet points with only what matters to the reader: dates, deadlines, amounts, \
order or tracking numbers, status changes, and what (if anything) they need to do. \
Skip greetings, boilerplate, and unsubscribe text. A promo needs at most one bullet."""


class EmailAnalysis(BaseModel):
    category: str
    label: Literal["action needed", "update", "promo"]
    bullets: list[str]


def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def analyze_email(client: anthropic.Anthropic, email: Email, categories: list[Category]) -> EmailAnalysis:
    category_list = "\n".join(f"- {c.name}: {c.description}" for c in categories)
    if not any(c.name == "other" for c in categories):
        category_list += "\n- other: anything that doesn't fit above"
    content = (
        f"Categories:\n{category_list}\n\n"
        f"From: {email.from_name or ''} <{email.from_address or ''}>\n"
        f"Subject: {email.subject or ''}\n"
        f"Date: {email.received_at}\n\n"
        f"{(email.body or '')[:MAX_BODY_CHARS]}"
    )

    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": content}],
        output_format=EmailAnalysis,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"Claude did not return an analysis (stop_reason={response.stop_reason})")
    return response.parsed_output


def analyze_pending() -> dict:
    """Analyze every email that has no summary yet. Returns how many were done."""
    if not has_api_key():
        return {"analyzed": 0, "skipped_reason": "no ANTHROPIC_API_KEY set"}

    client = anthropic.Anthropic()
    db = SessionLocal()
    categories = db.query(Category).all()
    names = {c.name for c in categories}

    pending = db.query(Email).filter(Email.summary.is_(None)).all()
    done, failed = 0, 0
    for email in pending:
        try:
            result = analyze_email(client, email, categories)
        except (anthropic.APIError, RuntimeError) as exc:
            print(f"Skipping email {email.id}: {exc}")
            failed += 1
            continue

        # A tracked sender's category wins over Claude's guess.
        if not email.category:
            email.category = result.category if result.category in names else "other"
        email.classification = result.label
        email.summary = "\n".join(result.bullets)
        db.commit()
        done += 1

    db.close()
    return {"analyzed": done, "failed": failed}


if __name__ == "__main__":
    print(analyze_pending())
