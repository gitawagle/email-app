import base64
from email.utils import parsedate_to_datetime

from database import SessionLocal
from gmail_auth import get_gmail_service
from models import Email, TrackedSender


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")


def extract_body(payload) -> str:
    body = payload.get("body", {})
    if payload.get("mimeType") == "text/plain" and "data" in body:
        return _decode(body["data"])

    parts = payload.get("parts") or []
    for part in parts:
        if part.get("mimeType") == "text/plain" and "data" in part.get("body", {}):
            return _decode(part["body"]["data"])

    for part in parts:
        if part.get("mimeType") == "text/html" and "data" in part.get("body", {}):
            return _decode(part["body"]["data"])

    for part in parts:
        nested = extract_body(part)
        if nested:
            return nested

    return ""


def get_header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return None


def ingest():
    service = get_gmail_service()
    db = SessionLocal()

    senders = db.query(TrackedSender).all()
    if not senders:
        print("No tracked senders yet - add some via the API first.")
        return

    total_new = 0
    for sender in senders:
        response = (
            service.users()
            .messages()
            .list(userId="me", q=f"from:{sender.email_address}")
            .execute()
        )
        message_ids = [m["id"] for m in response.get("messages", [])]
        new_for_sender = 0

        for message_id in message_ids:
            already_stored = (
                db.query(Email).filter(Email.gmail_message_id == message_id).first()
            )
            if already_stored:
                continue

            msg = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            headers = msg["payload"].get("headers", [])
            subject = get_header(headers, "Subject")
            date_str = get_header(headers, "Date")

            try:
                received_at = parsedate_to_datetime(date_str) if date_str else None
            except (TypeError, ValueError):
                received_at = None

            db.add(
                Email(
                    gmail_message_id=message_id,
                    sender_id=sender.id,
                    subject=subject,
                    received_at=received_at,
                    body=extract_body(msg["payload"]),
                )
            )
            new_for_sender += 1

        db.commit()
        print(f"{sender.email_address}: {len(message_ids)} found, {new_for_sender} new")
        total_new += new_for_sender

    print(f"Done. {total_new} new emails stored total.")
    db.close()


if __name__ == "__main__":
    ingest()
