import base64
import html
import re
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser

from database import SessionLocal
from gmail_auth import get_gmail_service
from models import Email, TrackedSender

INBOX_LIMIT = 100  # newest N inbox messages checked on each run


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")


class _TextExtractor(HTMLParser):
    """Turns an HTML email into readable text, dropping styles and scripts."""

    BLOCK_TAGS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table", "td"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "head"):
            self._skip += 1
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script", "head") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


# Invisible characters marketing emails use as preview-text padding.
_INVISIBLE = re.compile(r"[\u034f\u00ad\u200b-\u200f\u2007\u2060\ufeff]+")


def clean_text(text: str) -> str:
    text = _INVISIBLE.sub("", html.unescape(text)).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()


def html_to_text(markup: str) -> str:
    parser = _TextExtractor()
    parser.feed(markup)
    return "".join(parser.parts)


def _find_part(payload, mime_type):
    """Depth-first search for the first part with this mime type that has inline data."""
    if payload.get("mimeType") == mime_type and payload.get("body", {}).get("data"):
        return _decode(payload["body"]["data"])
    for part in payload.get("parts") or []:
        found = _find_part(part, mime_type)
        if found:
            return found
    return None


def extract_body(payload) -> str:
    plain = _find_part(payload, "text/plain")
    if plain and plain.strip():
        return clean_text(plain)
    markup = _find_part(payload, "text/html")
    return clean_text(html_to_text(markup)) if markup else ""


def get_header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return None


def ingest(limit: int = INBOX_LIMIT) -> dict:
    """Store any of the newest `limit` inbox messages not already saved. Returns counts."""
    service = get_gmail_service()
    db = SessionLocal()

    senders_by_address = {s.email_address.lower(): s for s in db.query(TrackedSender).all()}

    response = (
        service.users()
        .messages()
        .list(userId="me", labelIds=["INBOX"], maxResults=limit)
        .execute()
    )
    message_ids = [m["id"] for m in response.get("messages", [])]

    new_count = 0
    for message_id in message_ids:
        if db.query(Email).filter(Email.gmail_message_id == message_id).first():
            continue

        msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = msg["payload"].get("headers", [])
        from_name, from_address = parseaddr(get_header(headers, "From") or "")
        date_str = get_header(headers, "Date")

        try:
            received_at = parsedate_to_datetime(date_str) if date_str else None
        except (TypeError, ValueError):
            received_at = None

        sender = senders_by_address.get(from_address.lower())
        db.add(
            Email(
                gmail_message_id=message_id,
                sender_id=sender.id if sender else None,
                category=sender.category if sender else None,
                from_name=from_name or None,
                from_address=from_address or None,
                subject=get_header(headers, "Subject"),
                received_at=received_at,
                body=extract_body(msg["payload"]),
            )
        )
        new_count += 1

    db.commit()
    db.close()
    print(f"Checked {len(message_ids)} inbox messages, {new_count} new.")
    return {"checked": len(message_ids), "total_new": new_count}


if __name__ == "__main__":
    ingest()
