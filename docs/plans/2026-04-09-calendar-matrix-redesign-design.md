# Calendar & Matrix Interconnection — Design Doc

**Date:** 2026-04-09  
**Status:** Approved  
**Scope:** Full calendar UI overhaul + matrix→schedule→calendar interconnection

---

## Problem Summary

1. **Timezone bug** — backend stores naive UTC datetimes; create-event flow sends local time as if UTC, causing schedule blocks and manual events to appear at wrong times.
2. **Calendar UI** — tiles are cramped, no click-to-create, no drag-to-reschedule, month/week views are minimal.
3. **Matrix→Calendar gap** — moving a task on the matrix does not rebuild the schedule or refresh the calendar. All three views are siloed.

---

## Approach

Custom build extending the existing calendar page. No calendar library. Consistent with the existing Tailwind/shadcn/framer-motion design language.

---

## Section 1: Timezone Fix

**Root cause:** `datetime.utcnow()` produces naive datetimes throughout the backend (scheduler, calendar event creation). The frontend's `parseLocal()` appends `Z` to force UTC interpretation on display — correct for reading. But the create-event path sends local time strings without converting to UTC first, so a "9pm local" event in UTC-5 is stored as `21:00` instead of `02:00+00:00`.

**Fix — frontend:** All event create/edit submissions convert local datetime inputs to UTC via `new Date(localString).toISOString()` before sending to the API.

**Fix — backend scheduler:** The schedule runner computes energy windows (peak/mid/low) using clock hours. We add a `timezone` field to the User model (string, defaults to `"UTC"`). The scheduler converts "8am local" to the correct UTC offset when creating `ScheduleBlock` rows. The user's timezone is detected in the browser on first login and stored via `PATCH /api/users/me`.

**Backend schema change:** `users` table gets a `timezone` column (String, nullable, default `"UTC"`). Alembic migration required.

---

## Section 2: Calendar UI Components

### Tile Rendering
- 1 hour = 60px row height. Event height = `(duration_minutes / 60) * 60px`, minimum 24px.
- Colored left-border accent: blue=task block, red=deadline, amber=manual event, dashed gray=prep block.
- Tile shows: title (bold), time range (small), effort dots for task blocks.
- Tiles < 30 min show title only.
- Hover state: subtle shadow lift.

### Click-to-Create
- Clicking an empty area of the time grid opens a compact inline popover anchored to the clicked slot.
- Popover fields: title (auto-focused), start time (pre-filled), end time (pre-filled = start + 1h), save/cancel.
- On save: `POST /api/calendar/events` with UTC-converted times. New tile appears immediately (optimistic).

### Drag-to-Reschedule
- Events drag vertically (Y-axis only) within the time grid column.
- Snap to 15-minute intervals.
- Ghost tile shows target position during drag.
- On drop:
  - Manual event (`entry_type === "event"`) → `PATCH /api/calendar/events/{id}` with new start/end.
  - Task block (`entry_type === "block"`) → `PATCH /api/tasks/{id}` with new `scheduled_time`, then lightweight schedule re-sort (not full rebuild).
- Dragging task blocks across days (in week view) triggers a full `POST /api/schedule/rebuild`.

### Month View
- Clickable day cells. Clicking a day navigates to day view for that date.
- Events as pills: colored left dot + truncated title.
- "+N more" pill opens a popover listing all events for that day.

### Week View
- 7-column time grid (same renderer as day view, just more columns).
- Day headers highlight today.
- Horizontal scroll on mobile if viewport < 640px.

### Toolbar Additions
- "Add event" button (opens click-to-create form for current anchor time).
- "Sync schedule" button — triggers `POST /api/schedule/rebuild` and refreshes blocks.

---

## Section 3: Matrix → Schedule → Calendar Interconnection

### Data Flow
```
Matrix (urgency/importance change)
  → PATCH /api/tasks/{id}
  → POST /api/schedule/rebuild   [background, non-blocking]
  → Calendar refetches blocks    [via shared schedule store]

Calendar (drag task block to new time)
  → PATCH /api/tasks/{id} scheduled_time
  → lightweight re-sort of existing blocks
  → calendar re-renders

Calendar (create manual event)
  → POST /api/calendar/events
  → next schedule rebuild respects this slot as blocked
```

### Shared Schedule Store
A lightweight React context (`ScheduleContext`) with:
- `blocks: Block[]` — current schedule blocks
- `refresh()` — fetches `/api/schedule` and `/api/calendar/events` and merges
- `rebuildAndRefresh()` — calls `/api/schedule/rebuild` then `refresh()`

Both the matrix page and calendar page consume this context. Matrix moves call `rebuildAndRefresh()` after the task PATCH resolves. Calendar consumes `blocks` directly.

### Manual Events → Scheduler Awareness
The schedule runner already queries `CalendarEvent` rows to find blocked slots (or will after this change). When building the schedule, it will skip any time ranges occupied by existing calendar events for that user.

---

## Files Changed

### Backend
- `backend/app/models/user.py` — add `timezone` column
- `backend/alembic/versions/` — new migration for `timezone` column
- `backend/app/schemas/auth.py` — expose `timezone` in user response
- `backend/app/routers/users.py` — accept `timezone` in PATCH
- `backend/app/services/schedule_runner.py` — use user timezone for energy window calculation

### Frontend
- `frontend/src/lib/schedule-store.ts` — new shared schedule context
- `frontend/src/app/calendar/page.tsx` — full rewrite (drag, click-to-create, proper tiles)
- `frontend/src/app/matrix/page.tsx` — call `rebuildAndRefresh()` after move
- `frontend/src/app/layout.tsx` or `AppLayout` — wrap with `ScheduleProvider`

---

## Out of Scope (this iteration)
- Google Calendar API OAuth sync
- Recurring events UI
- Multi-day event spanning (all-day events shown in header only)
- Mobile native drag (tap-to-move via bottom sheet instead)
