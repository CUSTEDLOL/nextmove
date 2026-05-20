# NextMove — CLAUDE.md

> Read this file at the start of every session. It is the source of truth.

---

## What Is NextMove?

NextMove is an AI-powered productivity system built for **students**. It ingests unstructured commitments (brain dumps, calendar events, emails) and surfaces exactly **one primary task** per day. All prioritization and scheduling complexity is hidden from the user. The system does the thinking; the user executes.

**Core UX Principle:** The user sees TODAY'S ONE TASK + 2–3 secondary tasks. Nothing else.

---

## Product Decisions (Locked)

| Decision | Choice |
|---|---|
| Target users | Students |
| AI provider | OpenAI API (GPT-4o) |
| Primary interfaces | Telegram bot (full control) + Web app (full) |
| Calendar | Google Calendar (read + write) OR built-in calendar (Cal.com style) |
| Auth | Google OAuth OR email/password |
| Language | English only |
| Starting point | Scratch |
| Effort inference | User-stated in MVP; hybrid (AI-assisted) in later phases |

---

## Tech Stack

```
Backend         Python 3.12, FastAPI, SQLAlchemy, Alembic
Database        PostgreSQL 16, Redis (queues + caching)
AI              OpenAI API (gpt-4o for parsing, scoring, nudges)
Telegram        python-telegram-bot v20+
Web Frontend    Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui
Auth            NextAuth.js (web) + Google OAuth + JWT
Calendar        Google Calendar API v3 + built-in calendar (fallback)
Infra           Docker Compose (local), Railway or Render (prod)
Testing         pytest (backend), Jest + Testing Library (frontend)
```

---

## Repository Structure

```
nextmove/
├── CLAUDE.md                   ← you are here
├── docker-compose.yml
├── .env.example
│
├── backend/
│   ├── app/
│   │   ├── main.py             ← FastAPI app entry
│   │   ├── config.py           ← settings via pydantic-settings
│   │   ├── database.py         ← SQLAlchemy engine + session
│   │   ├── models/             ← SQLAlchemy ORM models
│   │   ├── schemas/            ← Pydantic request/response schemas
│   │   ├── routers/            ← FastAPI routers (auth, tasks, schedule, etc.)
│   │   ├── services/           ← Business logic (AI, scheduling, calendar)
│   │   │   ├── ai_parser.py
│   │   │   ├── matrix_scorer.py
│   │   │   ├── scheduler.py
│   │   │   ├── calendar_google.py
│   │   │   ├── calendar_builtin.py
│   │   │   ├── notifier.py
│   │   │   └── behavior_learner.py
│   │   ├── telegram/           ← Telegram bot handlers
│   │   └── workers/            ← Background jobs (Redis queues)
│   ├── tests/
│   ├── alembic/                ← DB migrations
│   └── requirements.txt
│
├── frontend/
│   ├── app/                    ← Next.js App Router
│   ├── components/
│   ├── lib/
│   └── package.json
│
└── docs/
    ├── PRODUCT.md
    ├── ARCHITECTURE.md
    └── plans/
```

---

## Core Domain Concepts

### Priority Index
```
P = 0.35 × Urgency + 0.30 × Importance + 0.20 × Effort + 0.15 × Dependency
```
Scores are 0–10. Higher P = shown first. Recalculated on: task add, deadline change, task complete.

### Task States
`pending` → `scheduled` → `in_progress` → `completed` | `missed` → `rescheduled`

### Energy Windows
- Peak (morning): heavy tasks (Effort ≥ 7)
- Mid (afternoon): medium tasks (Effort 4–6)
- Low (evening): light tasks (Effort ≤ 3)

### Notification Types
- Morning Brief (8am): today's #1 task + schedule
- Pre-task Prompt (15 min before): motivational nudge
- Procrastination Interrupt: triggered after 30 min inactivity on active task
- Evening Wrap-up (9pm): what was done, what to reschedule
- Weekly Summary (Sunday 7pm): patterns + next week preview

---

## Key Rules for Development

1. **Always TDD** — write failing test first, then implement.
2. **Never expose complexity to users** — the UI shows one task. All scoring/scheduling is backend-only.
3. **Telegram = full parity** — every action possible in the web app must be possible in Telegram.
4. **Calendar fallback** — if no Google Calendar linked, use built-in calendar. Never fail silently.
5. **Effort is user-stated** in Phase 1. Do not infer it automatically yet.
6. **OpenAI calls are async** — never block the request thread.
7. **Idempotent scheduling** — re-running the scheduler on the same state must produce the same result.
8. **Migrations only via Alembic** — never alter DB schema manually.
9. **No secrets in code** — all config via `.env` + `pydantic-settings`.

---

## Local Development Commands

```bash
# Start everything
docker-compose up

# Backend only
cd backend && uvicorn app.main:app --reload

# Run backend tests
cd backend && pytest -v

# Run frontend
cd frontend && npm run dev

# Create DB migration
cd backend && alembic revision --autogenerate -m "description"

# Apply migrations
cd backend && alembic upgrade head
```

---

## Environment Variables (see .env.example)

```
DATABASE_URL
REDIS_URL
OPENAI_API_KEY
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
TELEGRAM_BOT_TOKEN
JWT_SECRET_KEY
NEXTAUTH_SECRET
NEXTAUTH_URL
```

---

## Phase Roadmap

| Phase | Scope |
|---|---|
| 1 — Foundation | Auth, DB, AI parser, matrix scorer, scheduling engine, basic Telegram bot, basic web app |
| 2 — Intelligence | Behavior learning, Gmail scanning, weekly insights |
| 3 — Polish | Hybrid effort inference, mobile app, advanced nudges |
