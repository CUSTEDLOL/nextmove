# NextMove — System Architecture

## High-Level Flow

```
User (Telegram / Web App)
        │
        ▼
   FastAPI Backend
        │
   ┌────┴─────────────────────┐
   │                          │
AI Parser (OpenAI)    Matrix Scorer
   │                          │
   └────────────┬─────────────┘
                │
        Scheduling Engine
                │
   ┌────────────┴─────────────┐
   │                          │
Google Calendar          Built-in Calendar
(read + write)           (PostgreSQL)
                │
        Notification Engine
                │
   ┌────────────┴─────────────┐
   │                          │
Telegram Bot          Web Push / Email
```

---

## Component Breakdown

### 1. Input Capture Layer
Accepts tasks from:
- Web app (REST API)
- Telegram bot (webhook)
- [Phase 2] Gmail API

Entry point: `POST /api/tasks/dump` (brain dump) or `POST /api/tasks` (single task)

### 2. AI Parsing Engine (`services/ai_parser.py`)
- Input: raw natural language string
- Model: `gpt-4o` with structured output (JSON mode)
- Output: list of `{title, deadline, effort, context, dependencies[]}`
- Caches identical inputs in Redis (1hr TTL) to save tokens

### 3. Matrix Scoring Engine (`services/matrix_scorer.py`)
- Pure Python, no AI calls
- Formula: `P = 0.35U + 0.30I + 0.20E + 0.15D` (all scores 0–10)
- Urgency: derived from deadline proximity
- Importance: user-stated (1–5 mapped to 0–10)
- Effort: user-stated (Low/Medium/High mapped to 0–10)
- Dependency: number of tasks blocked by this one
- Triggered by: task add, deadline change, task complete, manual recalculate

### 4. Scheduling Engine (`services/scheduler.py`)
- Reads: user's free slots (Google Calendar or built-in)
- Reads: task list sorted by priority index
- Assigns: time blocks respecting energy windows
  - Peak (6am–12pm): Effort ≥ 7
  - Mid (12pm–6pm): Effort 4–6
  - Low (6pm–11pm): Effort ≤ 3
- Idempotent: same inputs → same schedule
- Writes: back to Google Calendar or built-in calendar

### 5. Built-in Calendar (`services/calendar_builtin.py`)
- PostgreSQL-backed time block system
- Supports: recurring events, all-day events, time blocks
- API mirrors Google Calendar API shape for easy swap
- Used when user has not connected Google Calendar

### 6. Google Calendar Integration (`services/calendar_google.py`)
- OAuth2 token stored per user (encrypted in DB)
- Read: list events, find free slots
- Write: create/update/delete events for scheduled tasks
- Refresh token handled automatically

### 7. Telegram Bot (`telegram/`)
- Library: `python-telegram-bot` v20 (async)
- Webhook-based (not polling) in production
- ConversationHandler for multi-step flows (brain dump, procrastination)
- InlineKeyboard for all interactions
- Full feature parity with web app

### 8. Notification Engine (`services/notifier.py`)
- Runs as background worker (Redis queue via `rq`)
- Schedule: cron-like jobs per user based on their timezone
- Types: morning_brief, pre_task, procrastination_interrupt, evening_wrapup, weekly_summary
- Delivery: Telegram (primary), email (fallback, Phase 2)

### 9. Behavior Learning Engine (`services/behavior_learner.py`) [Phase 2]
- Inputs: actual task start/end times, completion vs scheduled
- Outputs: updated energy profile per user
- Runs: weekly batch job

---

## Database Schema

```sql
-- Users
users (
  id UUID PK,
  email TEXT UNIQUE,
  name TEXT,
  timezone TEXT DEFAULT 'UTC',
  google_access_token TEXT,       -- encrypted
  google_refresh_token TEXT,      -- encrypted
  telegram_chat_id BIGINT,
  uses_google_calendar BOOLEAN DEFAULT false,
  study_start_hour INT DEFAULT 9, -- user's typical study window start
  study_end_hour INT DEFAULT 22,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
)

-- Tasks
tasks (
  id UUID PK,
  user_id UUID FK → users,
  title TEXT NOT NULL,
  raw_input TEXT,                 -- original brain dump text segment
  deadline TIMESTAMPTZ,
  effort TEXT CHECK (effort IN ('low','medium','high')),
  importance INT CHECK (1..5),
  context TEXT,                   -- 'Study', 'Admin', 'Personal', etc.
  priority_index FLOAT,           -- computed: P = 0.35U + 0.30I + 0.20E + 0.15D
  status TEXT CHECK (status IN ('pending','scheduled','in_progress','completed','missed','rescheduled')),
  parent_task_id UUID FK → tasks, -- for dependencies
  google_event_id TEXT,           -- if synced to Google Calendar
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
)

-- Scheduled Blocks
schedule_blocks (
  id UUID PK,
  task_id UUID FK → tasks,
  user_id UUID FK → users,
  start_time TIMESTAMPTZ NOT NULL,
  end_time TIMESTAMPTZ NOT NULL,
  is_google_synced BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ
)

-- Built-in Calendar Events (when no Google Calendar)
calendar_events (
  id UUID PK,
  user_id UUID FK → users,
  title TEXT,
  start_time TIMESTAMPTZ,
  end_time TIMESTAMPTZ,
  is_all_day BOOLEAN DEFAULT false,
  recurrence_rule TEXT,           -- iCal RRULE format
  source TEXT DEFAULT 'manual',   -- 'manual', 'nextmove', 'google_import'
  created_at TIMESTAMPTZ
)

-- Productivity Logs
productivity_logs (
  id UUID PK,
  task_id UUID FK → tasks,
  user_id UUID FK → users,
  scheduled_start TIMESTAMPTZ,
  actual_start TIMESTAMPTZ,
  actual_end TIMESTAMPTZ,
  was_completed BOOLEAN,
  procrastination_detected BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ
)

-- Notification Log
notification_log (
  id UUID PK,
  user_id UUID FK → users,
  type TEXT,
  sent_at TIMESTAMPTZ,
  channel TEXT DEFAULT 'telegram'
)
```

---

## API Endpoints

```
Auth
  POST   /api/auth/register
  POST   /api/auth/login
  POST   /api/auth/google
  POST   /api/auth/refresh

Tasks
  POST   /api/tasks/dump          ← brain dump (NLP → multiple tasks)
  GET    /api/tasks               ← list (filter by status, date)
  POST   /api/tasks               ← single task add
  GET    /api/tasks/{id}
  PATCH  /api/tasks/{id}
  DELETE /api/tasks/{id}
  POST   /api/tasks/{id}/complete
  POST   /api/tasks/{id}/reschedule
  GET    /api/tasks/today         ← primary + secondary tasks for today

Schedule
  GET    /api/schedule            ← current week's blocks
  POST   /api/schedule/rebuild    ← trigger full reschedule
  GET    /api/schedule/free-slots ← available slots

Calendar
  GET    /api/calendar/events     ← built-in calendar events
  POST   /api/calendar/events
  PATCH  /api/calendar/events/{id}
  DELETE /api/calendar/events/{id}
  POST   /api/calendar/google/connect
  DELETE /api/calendar/google/disconnect

Users
  GET    /api/users/me
  PATCH  /api/users/me
  GET    /api/users/me/stats      ← completion rate, streaks

Telegram
  POST   /api/telegram/webhook    ← Telegram webhook receiver
```

---

## Infrastructure

```
docker-compose services:
  postgres    — PostgreSQL 16
  redis       — Redis 7
  backend     — FastAPI (uvicorn)
  worker      — RQ worker (notifications, background jobs)
  frontend    — Next.js (dev) / nginx (prod)
  ngrok       — Telegram webhook tunnel (dev only)
```

Production: Railway (backend + postgres + redis) + Vercel (frontend)
