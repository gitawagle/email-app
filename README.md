# Email App

A personal Gmail inbox tracker: ingests your inbox, sorts emails into
categories, and (optionally) uses Claude to summarize and label each one.

## Stack

- **Backend**: FastAPI + SQLAlchemy (SQLite), in `app/`
- **Frontend**: React + Vite, in `frontend/`
- **Gmail**: read-only OAuth via `app/credentials.json` / `app/token.json`
- **Analysis**: Claude API (optional — skipped if no API key)

## Setup

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

Gmail OAuth credentials (`app/credentials.json`) must be downloaded from
Google Cloud Console first; running the backend will open a browser login
the first time and save `app/token.json`.

For Claude-powered summaries, add a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-...
```

## Run

```bash
# Terminal 1 — backend (http://localhost:8000)
cd app && uvicorn main:app --reload --port 8000



# Terminal 2 — frontend (http://localhost:5173)
cd frontend && npm run dev
```
<img width="963" height="510" alt="Screenshot 2026-11-10 at 7 19 25 PM" src="https://github.com/user-attachments/assets/518e12c7-1994-4593-92bf-4eb9b5ed8f28" />


