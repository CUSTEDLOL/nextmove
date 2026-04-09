# Calendar & Matrix Interconnection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the calendar timezone bug, rebuild the calendar UI to match Google Calendar UX (click-to-create, drag-to-reschedule, proper tile sizing across day/week/month views), and wire the matrix → schedule → calendar chain so moving a task in the matrix automatically rebuilds the schedule and the calendar reflects it.

**Architecture:** Custom build on top of the existing calendar page. A shared `ScheduleContext` (React context) holds block data; both the matrix page and the calendar consume it. The backend already blocks out `CalendarEvent` rows in free-slot computation — we just need to thread the user's timezone through the scheduler so blocks land at the correct local times. Drag-to-reschedule uses native mouse events with a ghost tile overlay; no third-party drag library.

**Tech Stack:** Next.js 14 (App Router), TypeScript, Tailwind CSS, React context, Node built-in test runner (frontend pure-logic tests), pytest (backend), `zoneinfo` (Python 3.12 stdlib — no new packages)

---

### Task 1: Backend — Thread user timezone through the scheduler

**Root cause of 9pm bug:** `calendar_builtin.py` calls `date.replace(hour=study_start)` where `date` comes from `datetime.utcnow()`. This computes "9am" in UTC, not the user's local time. A user in UTC+8 whose study window starts at 9am local gets blocks stored at 01:00 UTC, which `parseLocal()` on the frontend correctly shows as 9am — that part is fine. But until now, `study_start` was being applied in UTC, so a UTC+8 user would see blocks at 5pm local instead of 9am.

The fix: pass `user.timezone` through to `get_builtin_free_slots` and use `zoneinfo.ZoneInfo` to convert the local study hours to their correct UTC equivalent.

**Files:**
- Modify: `backend/app/services/calendar_builtin.py`
- Modify: `backend/app/services/schedule_runner.py`
- Test: `backend/tests/test_schedule_api.py`

**Step 1: Write a failing test that verifies a UTC+8 user's blocks start at 01:00 UTC (= 9am local)**

Add to `backend/tests/test_schedule_api.py`:

```python
def test_schedule_respects_user_timezone():
    """A UTC+8 user with study_start=9 should get blocks starting at 01:00 UTC."""
    from app.services.schedule_runner import run_schedule_for_user
    from app.models import Task, ScheduleBlock
    db = TestingSession()
    try:
        tz_user_id = uuid.uuid4()
        tz_user = User(
            id=tz_user_id,
            email=f"tz_{tz_user_id}@uni.edu",
            name="TZ Tester",
            timezone="Asia/Singapore",   # UTC+8
            study_start_hour=9,
            study_end_hour=22,
        )
        db.add(tz_user)
        db.add(Task(
            user_id=tz_user_id,
            title="TZ test task",
            effort="low",
            priority_index=5.0,
            status="pending",
        ))
        db.commit()

        from datetime import timezone as dt_timezone
        # Simulate scheduler running at 00:00 UTC = 08:00 Asia/Singapore on 2026-04-09
        reference_utc = datetime(2026, 4, 9, 0, 0, 0)
        blocks = run_schedule_for_user(tz_user, db, date=reference_utc)
        assert len(blocks) >= 1
        # First block should start at 01:00 UTC (= 09:00 Asia/Singapore)
        assert blocks[0].start_time.hour == 1
    finally:
        db.query(ScheduleBlock).filter(ScheduleBlock.user_id == tz_user_id).delete()
        db.query(Task).filter(Task.user_id == tz_user_id).delete()
        db.query(User).filter(User.id == tz_user_id).delete()
        db.commit()
        db.close()
```

**Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_schedule_api.py::test_schedule_respects_user_timezone -v
```

Expected: FAIL — blocks start at 09:00 UTC instead of 01:00 UTC.

**Step 3: Fix `calendar_builtin.py` to use the user's timezone**

Replace the entire file:

```python
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from app.services.scheduler import FreeSlot

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    import uuid


def get_builtin_free_slots(
    user_id: "uuid.UUID",
    date: datetime,
    study_start: int = 9,
    study_end: int = 22,
    db: "Session" = None,
    tz_str: str = "UTC",
) -> list[FreeSlot]:
    """Find free time blocks using the built-in calendar (no Google).

    `date` is a naive UTC datetime.  We convert it to the user's local
    timezone, compute the study window in local time, then convert back
    to naive UTC for storage — so blocks land at the correct wall-clock
    hours for the user.
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        tz = ZoneInfo(tz_str)
    except (ZoneInfoNotFoundError, KeyError):
        tz = ZoneInfo("UTC")

    utc_dt = date.replace(tzinfo=ZoneInfo("UTC"))
    local_dt = utc_dt.astimezone(tz)

    local_day_start = local_dt.replace(hour=study_start, minute=0, second=0, microsecond=0)
    local_day_end = local_dt.replace(hour=study_end, minute=0, second=0, microsecond=0)

    # Convert back to naive UTC for DB storage
    day_start = local_day_start.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    day_end = local_day_end.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    if db is None:
        return [FreeSlot(start=day_start, end=day_end)]

    from app.models import CalendarEvent
    events = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.user_id == user_id,
            CalendarEvent.start_time < day_end,
            CalendarEvent.end_time > day_start,
        )
        .order_by(CalendarEvent.start_time)
        .all()
    )

    free = []
    cursor = day_start
    for e in events:
        if cursor < e.start_time:
            free.append(FreeSlot(start=cursor, end=e.start_time))
        cursor = max(cursor, e.end_time)
    if cursor < day_end:
        free.append(FreeSlot(start=cursor, end=day_end))

    return free
```

**Step 4: Thread `user.timezone` through `schedule_runner.py`**

In `backend/app/services/schedule_runner.py`, update the two call sites:

```python
def _get_free_slots(user: User, date: datetime, db: Session, study_start: int = 9, study_end: int = 22) -> list[FreeSlot]:
    tz_str = user.timezone or "UTC"
    if user.uses_google_calendar and user.google_access_token:
        try:
            from app.services.calendar_google import get_google_service, get_free_slots as gcal_free
            service = get_google_service(user.google_access_token, user.google_refresh_token)
            slots = gcal_free(service, "primary", date, study_start, study_end)
            return [FreeSlot(start=s.start, end=s.end) for s in slots]
        except Exception:
            pass

    return get_builtin_free_slots(user.id, date, study_start, study_end, db, tz_str=tz_str)
```

**Step 5: Run the test to verify it passes**

```bash
cd backend && pytest tests/test_schedule_api.py::test_schedule_respects_user_timezone -v
```

Expected: PASS

**Step 6: Run full backend test suite**

```bash
cd backend && pytest -v
```

Expected: all tests pass.

**Step 7: Commit**

```bash
git add backend/app/services/calendar_builtin.py backend/app/services/schedule_runner.py backend/tests/test_schedule_api.py
git commit -m "fix(scheduler): thread user timezone through free-slot computation — fixes 9pm → wrong time bug"
```

---

### Task 2: Frontend — Calendar utility functions + tests

Pure time-math helpers that are easy to unit-test and are shared by the calendar page, click-to-create form, and drag handler.

**Files:**
- Create: `frontend/src/lib/calendar-utils.ts`
- Create: `frontend/src/lib/calendar-utils.test.ts`

**Step 1: Write the failing tests**

Create `frontend/src/lib/calendar-utils.test.ts`:

```ts
import test from "node:test"
import assert from "node:assert/strict"
import {
  snapToInterval,
  localInputToUtc,
  minsFromHourStart,
  pxFromMins,
  minsFromPx,
} from "./calendar-utils.ts"

test("snapToInterval rounds down to nearest 15 min", () => {
  assert.equal(snapToInterval(7, 15), 0)
  assert.equal(snapToInterval(15, 15), 15)
  assert.equal(snapToInterval(22, 15), 15)
  assert.equal(snapToInterval(45, 15), 45)
  assert.equal(snapToInterval(59, 15), 45)
})

test("snapToInterval works for 30-min intervals", () => {
  assert.equal(snapToInterval(0, 30), 0)
  assert.equal(snapToInterval(29, 30), 0)
  assert.equal(snapToInterval(30, 30), 30)
})

test("localInputToUtc converts datetime-local string to ISO UTC", () => {
  // We can only test the format, not the exact offset (depends on TZ env)
  const result = localInputToUtc("2026-04-09T09:00")
  assert.ok(result.endsWith("Z"), `expected Z suffix, got ${result}`)
  assert.ok(result.includes("T"), "expected ISO T separator")
})

test("minsFromHourStart computes offset from grid start", () => {
  // A date at 09:30 local with HOUR_START=7 => 150 mins
  const d = new Date("2026-04-09T09:30:00")
  assert.equal(minsFromHourStart(d, 7), 150)
})

test("pxFromMins and minsFromPx are inverse at HOUR_PX=60", () => {
  assert.equal(pxFromMins(60, 60), 60)
  assert.equal(pxFromMins(30, 60), 30)
  assert.equal(minsFromPx(60, 60), 60)
  assert.equal(minsFromPx(30, 60), 30)
})
```

**Step 2: Run to verify failure**

```bash
cd frontend && node --test src/lib/calendar-utils.test.ts 2>&1 | head -20
```

Expected: error — module not found.

**Step 3: Implement `calendar-utils.ts`**

Create `frontend/src/lib/calendar-utils.ts`:

```ts
/** Round `minutes` down to the nearest `intervalMins` boundary. */
export function snapToInterval(minutes: number, intervalMins: number): number {
  return Math.floor(minutes / intervalMins) * intervalMins
}

/**
 * Convert a `datetime-local` input value ("2026-04-09T21:00") to a UTC ISO
 * string ("2026-04-09T13:00:00.000Z" for UTC+8).
 * The browser interprets the bare string as local time, so `new Date()` gives
 * the correct UTC epoch and `.toISOString()` serialises it.
 */
export function localInputToUtc(localDatetimeStr: string): string {
  return new Date(localDatetimeStr).toISOString()
}

/**
 * Convert a UTC ISO string (or naive string from the backend) to a local Date.
 * Backend sends naive UTC datetimes — append "Z" so the browser treats them as UTC
 * and auto-converts to local time.
 */
export function parseLocal(s: string): Date {
  const normalized = s.includes("Z") || s.includes("+") ? s : s.replace(" ", "T") + "Z"
  return new Date(normalized)
}

/**
 * Minutes elapsed since `hourStart` for a given Date (in local time).
 * e.g. date=09:30, hourStart=7 → 150
 */
export function minsFromHourStart(date: Date, hourStart: number): number {
  return (date.getHours() - hourStart) * 60 + date.getMinutes()
}

/** Convert minutes to pixels given `hourPx` pixels per hour. */
export function pxFromMins(mins: number, hourPx: number): number {
  return (mins / 60) * hourPx
}

/** Convert pixels to minutes given `hourPx` pixels per hour. */
export function minsFromPx(px: number, hourPx: number): number {
  return (px / hourPx) * 60
}

/** Format a Date as "9:00 AM". */
export function fmtTime(d: Date): string {
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true })
}

/** Format a Date as "Apr 7". */
export function fmtMonthDay(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

/** Format an hour number as "9am" / "2pm". */
export function fmtHour(h: number): string {
  const ap = h < 12 ? "am" : "pm"
  const h12 = h % 12 === 0 ? 12 : h % 12
  return `${h12}${ap}`
}

/** "YYYY-M-D" key for grouping blocks by day. */
export function dayKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
}

export function startOfDay(d: Date): Date {
  const x = new Date(d)
  x.setHours(0, 0, 0, 0)
  return x
}

export function addDays(d: Date, n: number): Date {
  const x = new Date(d)
  x.setDate(x.getDate() + n)
  return x
}

export function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
}

/** Convert a local Date to a "datetime-local" input value ("2026-04-09T09:00"). */
export function toLocalInputValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
```

**Step 4: Run tests to verify they pass**

```bash
cd frontend && node --test src/lib/calendar-utils.test.ts
```

Expected: all 5 tests pass.

**Step 5: Commit**

```bash
git add frontend/src/lib/calendar-utils.ts frontend/src/lib/calendar-utils.test.ts
git commit -m "feat(calendar): add calendar utility functions with tests"
```

---

### Task 3: Frontend — Shared schedule store

A React context that both the matrix page and the calendar page use. This is the "glue" that makes matrix moves automatically refresh the calendar.

**Files:**
- Create: `frontend/src/lib/schedule-store.tsx`

**Step 1: Create the file**

```tsx
"use client"

import { createContext, useCallback, useContext, useEffect, useState } from "react"
import { api } from "@/lib/api"

export interface Block {
  id: string
  task_title: string
  effort: string | null
  start_time: string
  end_time: string
  entry_type: "block" | "deadline" | "prep" | "event"
}

interface ScheduleContextType {
  blocks: Block[]
  loading: boolean
  /** Re-fetch schedule blocks + calendar events without a rebuild. */
  refresh: () => Promise<void>
  /** Trigger a full schedule rebuild, then re-fetch. */
  rebuildAndRefresh: () => Promise<void>
}

const ScheduleContext = createContext<ScheduleContextType>({
  blocks: [],
  loading: true,
  refresh: async () => {},
  rebuildAndRefresh: async () => {},
})

export function ScheduleProvider({ children }: { children: React.ReactNode }) {
  const [blocks, setBlocks] = useState<Block[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const [scheduleBlocks, events] = await Promise.all([
        api.getScheduleBlocks(),
        api.getCalendarEvents(),
      ])
      const eventBlocks = (events as Array<Record<string, unknown>>).map((e) => ({
        id: `event-${String(e.id)}`,
        task_title: String(e.title),
        effort: null,
        start_time: String(e.start_time),
        end_time: String(e.end_time),
        entry_type: "event" as const,
      }))
      setBlocks([...(scheduleBlocks as Block[]), ...eventBlocks])
    } catch {
      // Keep stale data on network error.
    } finally {
      setLoading(false)
    }
  }, [])

  const rebuildAndRefresh = useCallback(async () => {
    try {
      await api.rebuildSchedule()
    } catch {
      // Even if rebuild fails, still refresh to show current state.
    }
    await refresh()
  }, [refresh])

  useEffect(() => {
    refresh()
  }, [refresh])

  return (
    <ScheduleContext.Provider value={{ blocks, loading, refresh, rebuildAndRefresh }}>
      {children}
    </ScheduleContext.Provider>
  )
}

export function useSchedule() {
  return useContext(ScheduleContext)
}
```

**Step 2: Commit**

```bash
git add frontend/src/lib/schedule-store.tsx
git commit -m "feat(calendar): add shared ScheduleContext — matrix + calendar share one data source"
```

---

### Task 4: Frontend — Wrap AppLayout with ScheduleProvider

**Files:**
- Modify: `frontend/src/components/layout/AppLayout.tsx`

**Step 1: Wrap the return with ScheduleProvider**

```tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { Sidebar } from "./Sidebar";
import { BottomTabBar } from "./BottomTabBar";
import { ScheduleProvider } from "@/lib/schedule-store";

export function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data: session, status } = useSession();
  const hasAccessToken = Boolean((session as { accessToken?: string } | null)?.accessToken);

  useEffect(() => {
    if (status !== "loading" && !hasAccessToken) {
      router.replace("/login");
    }
  }, [hasAccessToken, router, status]);

  if (status === "loading" || !hasAccessToken) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--background)] px-4">
        <p className="text-sm text-gray-500">Checking your session...</p>
      </div>
    );
  }

  return (
    <ScheduleProvider>
      <div className="flex min-h-screen bg-[var(--background)]">
        <Sidebar />
        <main className="flex-1 flex flex-col min-w-0">
          {children}
        </main>
        <BottomTabBar />
      </div>
    </ScheduleProvider>
  );
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "error|AppLayout" | head -10
```

Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/src/components/layout/AppLayout.tsx
git commit -m "feat(calendar): wrap AppLayout with ScheduleProvider"
```

---

### Task 5: Frontend — Full calendar page core (grid + tiles, all 3 views)

This is the main rewrite. The page is rebuilt around `useSchedule()` instead of its own local fetch. Tiles are properly proportional (1px per minute). The grid is scrollable.

**Constants:**
- `HOUR_PX = 60` — 60 pixels per hour (= 1px per minute)
- `HOUR_START = 7`, `HOUR_END = 23` — 7am–11pm
- Minimum tile height = 24px (for sub-30min events)

**Files:**
- Modify: `frontend/src/app/calendar/page.tsx`

**Step 1: Replace the entire file**

```tsx
"use client"

import { useRef, useState } from "react"
import { AppLayout } from "@/components/layout/AppLayout"
import { useSchedule, type Block } from "@/lib/schedule-store"
import {
  addDays,
  dayKey,
  fmtHour,
  fmtMonthDay,
  fmtTime,
  minsFromHourStart,
  parseLocal,
  pxFromMins,
  sameDay,
  snapToInterval,
  startOfDay,
  toLocalInputValue,
  localInputToUtc,
} from "@/lib/calendar-utils"
import { api } from "@/lib/api"
import { Plus, RefreshCw } from "lucide-react"

type View = "day" | "week" | "month"

const HOUR_PX = 60
const HOUR_START = 7
const HOUR_END = 23
const TOTAL_HOURS = HOUR_END - HOUR_START
const SNAP_MINS = 15

// ─── Styles ──────────────────────────────────────────────────────────────────

const BLOCK_COLORS: Record<Block["entry_type"], string> = {
  block: "bg-blue-50 border-blue-400 text-blue-900",
  deadline: "bg-red-50 border-red-400 text-red-800",
  prep: "bg-gray-50 border-gray-300 text-gray-500 border-dashed",
  event: "bg-amber-50 border-amber-400 text-amber-900",
}

const BLOCK_ACCENT: Record<Block["entry_type"], string> = {
  block: "bg-blue-400",
  deadline: "bg-red-400",
  prep: "bg-gray-300",
  event: "bg-amber-400",
}

// ─── Column overlap layout ────────────────────────────────────────────────────

function assignColumns(blocks: Block[]): { block: Block; col: number; totalCols: number }[] {
  const sorted = [...blocks].sort(
    (a, b) => parseLocal(a.start_time).getTime() - parseLocal(b.start_time).getTime()
  )
  const cols: { block: Block; col: number; end: Date }[] = []
  const result: { block: Block; col: number; totalCols: number }[] = []

  for (const b of sorted) {
    const start = parseLocal(b.start_time)
    const end = parseLocal(b.end_time)
    let col = 0
    while (cols[col] && cols[col].end > start) col++
    cols[col] = { block: b, col, end }
    result.push({ block: b, col, totalCols: 0 })
  }

  for (let i = 0; i < result.length; i++) {
    const start = parseLocal(result[i].block.start_time)
    const end = parseLocal(result[i].block.end_time)
    let maxCol = result[i].col
    for (let j = 0; j < result.length; j++) {
      const s2 = parseLocal(result[j].block.start_time)
      const e2 = parseLocal(result[j].block.end_time)
      if (s2 < end && e2 > start) maxCol = Math.max(maxCol, result[j].col)
    }
    result[i].totalCols = maxCol + 1
  }
  return result
}

// ─── Event tile ───────────────────────────────────────────────────────────────

interface TileProps {
  block: Block
  col: number
  totalCols: number
  onDragStart: (block: Block, offsetY: number) => void
}

function EventTile({ block, col, totalCols, onDragStart }: TileProps) {
  const start = parseLocal(block.start_time)
  const end = parseLocal(block.end_time)
  const startMins = Math.max(0, minsFromHourStart(start, HOUR_START))
  const rawDur = block.entry_type === "deadline" ? 30 : (end.getTime() - start.getTime()) / 60000
  const durMins = Math.min(rawDur, TOTAL_HOURS * 60 - startMins)
  const topPx = pxFromMins(startMins, HOUR_PX)
  const heightPx = Math.max(pxFromMins(durMins, HOUR_PX), 24)
  const colW = 100 / totalCols
  const isShort = heightPx < 40

  return (
    <div
      className={`absolute rounded-lg border-l-[3px] overflow-hidden cursor-grab active:cursor-grabbing select-none transition-shadow hover:shadow-md ${BLOCK_COLORS[block.entry_type]}`}
      style={{
        top: topPx,
        height: heightPx,
        left: `${col * colW + 0.5}%`,
        width: `${colW - 1}%`,
        zIndex: 10,
      }}
      onMouseDown={(e) => {
        e.stopPropagation()
        const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
        onDragStart(block, e.clientY - rect.top)
      }}
    >
      <div className="px-1.5 py-1 h-full flex flex-col justify-start overflow-hidden">
        <p className={`font-semibold leading-tight truncate ${isShort ? "text-[10px]" : "text-[11px]"}`}>
          {block.task_title}
        </p>
        {!isShort && (
          <p className="text-[10px] opacity-60 mt-0.5">
            {fmtTime(start)} – {fmtTime(end)}
          </p>
        )}
      </div>
    </div>
  )
}

// ─── Time grid (day + week) ───────────────────────────────────────────────────

interface TimeGridProps {
  days: Date[]
  blocks: Block[]
  onClickSlot: (day: Date, minutesFromStart: number) => void
  onDragStart: (block: Block, offsetY: number) => void
}

function TimeGrid({ days, blocks, onClickSlot, onDragStart }: TimeGridProps) {
  const now = new Date()
  const nowMins = minsFromHourStart(now, HOUR_START)
  const nowPx = pxFromMins(nowMins, HOUR_PX)
  const isNowVisible = nowMins >= 0 && nowMins <= TOTAL_HOURS * 60

  const blocksByDay: Record<string, Block[]> = {}
  for (const b of blocks) {
    const k = dayKey(parseLocal(b.start_time))
    if (!blocksByDay[k]) blocksByDay[k] = []
    blocksByDay[k].push(b)
  }

  const totalHeight = TOTAL_HOURS * HOUR_PX

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      {/* Gutter */}
      <div className="shrink-0 w-14 flex flex-col" style={{ paddingTop: 33 }}>
        <div className="relative" style={{ height: totalHeight }}>
          {Array.from({ length: TOTAL_HOURS }, (_, i) => (
            <div
              key={i}
              className="absolute w-full flex justify-end pr-2"
              style={{ top: i * HOUR_PX - 8 }}
            >
              <span className="text-[10px] text-gray-400">{fmtHour(HOUR_START + i)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Day columns — scrollable vertically */}
      <div className="flex-1 overflow-y-auto min-w-0">
        {/* Day headers — sticky */}
        <div
          className="sticky top-0 z-20 bg-white border-b border-gray-200 grid"
          style={{ gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))` }}
        >
          {days.map((day) => {
            const isToday = sameDay(day, now)
            return (
              <div key={dayKey(day)} className="flex items-center justify-center py-2 border-l border-gray-100">
                <span
                  className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                    isToday ? "bg-emerald-500 text-white" : "text-gray-500"
                  }`}
                >
                  {day.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
                </span>
              </div>
            )
          })}
        </div>

        {/* Grid body */}
        <div
          className="relative grid"
          style={{
            gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))`,
            height: totalHeight,
          }}
        >
          {/* Hour lines across all columns */}
          <div className="absolute inset-0 pointer-events-none">
            {Array.from({ length: TOTAL_HOURS }, (_, i) => (
              <div
                key={i}
                className="absolute w-full border-t border-gray-100"
                style={{ top: i * HOUR_PX }}
              />
            ))}
            {/* 30-min sub-lines */}
            {Array.from({ length: TOTAL_HOURS }, (_, i) => (
              <div
                key={`half-${i}`}
                className="absolute w-full border-t border-gray-50"
                style={{ top: i * HOUR_PX + HOUR_PX / 2 }}
              />
            ))}
          </div>

          {days.map((day) => {
            const isToday = sameDay(day, now)
            const dayBlocks = blocksByDay[dayKey(day)] ?? []
            const positioned = assignColumns(dayBlocks)

            return (
              <div
                key={dayKey(day)}
                className="relative border-l border-gray-100 cursor-pointer"
                onClick={(e) => {
                  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
                  const rawMins = ((e.clientY - rect.top) / HOUR_PX) * 60
                  const snapped = snapToInterval(Math.round(rawMins), SNAP_MINS)
                  onClickSlot(day, snapped)
                }}
              >
                {/* Current time indicator */}
                {isToday && isNowVisible && (
                  <div
                    className="absolute w-full z-20 flex items-center pointer-events-none"
                    style={{ top: nowPx }}
                  >
                    <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 -ml-1.5 shrink-0" />
                    <div className="flex-1 h-px bg-emerald-500" />
                  </div>
                )}

                {positioned.map(({ block, col, totalCols }) => (
                  <EventTile
                    key={block.id}
                    block={block}
                    col={col}
                    totalCols={totalCols}
                    onDragStart={onDragStart}
                  />
                ))}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ─── Month grid ───────────────────────────────────────────────────────────────

function MonthGrid({
  anchor,
  blocks,
  onDayClick,
}: {
  anchor: Date
  blocks: Block[]
  onDayClick: (day: Date) => void
}) {
  const year = anchor.getFullYear()
  const month = anchor.getMonth()
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  const startPad = firstDay.getDay()
  const cells: (Date | null)[] = [
    ...Array(startPad).fill(null),
    ...Array.from({ length: lastDay.getDate() }, (_, i) => new Date(year, month, i + 1)),
  ]
  while (cells.length % 7 !== 0) cells.push(null)

  const blocksByDay: Record<string, Block[]> = {}
  for (const b of blocks) {
    const k = dayKey(parseLocal(b.start_time))
    if (!blocksByDay[k]) blocksByDay[k] = []
    blocksByDay[k].push(b)
  }

  return (
    <div className="h-full flex flex-col">
      <div className="grid grid-cols-7 border-b border-gray-200 shrink-0">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
          <div key={d} className="text-center text-xs font-medium text-gray-400 py-2">
            {d}
          </div>
        ))}
      </div>
      <div className="flex-1 grid grid-cols-7 gap-px bg-gray-200 overflow-auto">
        {cells.map((day, i) => {
          if (!day) return <div key={i} className="bg-gray-50" />
          const isToday = sameDay(day, new Date())
          const dayBlocks = blocksByDay[dayKey(day)] ?? []
          return (
            <div
              key={i}
              className="bg-white p-1.5 overflow-hidden cursor-pointer hover:bg-gray-50 transition-colors"
              onClick={() => onDayClick(day)}
            >
              <p
                className={`text-xs font-semibold w-6 h-6 flex items-center justify-center rounded-full mb-1 ${
                  isToday ? "bg-emerald-500 text-white" : "text-gray-500"
                }`}
              >
                {day.getDate()}
              </p>
              <div className="space-y-0.5">
                {dayBlocks.slice(0, 3).map((b) => (
                  <div
                    key={b.id}
                    className={`text-[10px] px-1.5 py-0.5 rounded flex items-center gap-1 truncate ${BLOCK_COLORS[b.entry_type]}`}
                    title={b.task_title}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${BLOCK_ACCENT[b.entry_type]}`} />
                    {fmtTime(parseLocal(b.start_time)).replace(":00 ", " ")} {b.task_title}
                  </div>
                ))}
                {dayBlocks.length > 3 && (
                  <p className="text-[10px] text-gray-400 pl-1">+{dayBlocks.length - 3} more</p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Create event popover ─────────────────────────────────────────────────────

interface CreatePopoverProps {
  initialDay: Date
  initialMinsFromStart: number
  onSave: (title: string, startUtc: string, endUtc: string) => Promise<void>
  onClose: () => void
}

function CreatePopover({ initialDay, initialMinsFromStart, onSave, onClose }: CreatePopoverProps) {
  const startDate = new Date(initialDay)
  startDate.setHours(HOUR_START, 0, 0, 0)
  startDate.setMinutes(initialMinsFromStart)
  const endDate = new Date(startDate.getTime() + 60 * 60 * 1000) // +1 hour

  const [title, setTitle] = useState("")
  const [startVal, setStartVal] = useState(toLocalInputValue(startDate))
  const [endVal, setEndVal] = useState(toLocalInputValue(endDate))
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    if (!title.trim()) return
    setSaving(true)
    await onSave(title.trim(), localInputToUtc(startVal), localInputToUtc(endVal))
    setSaving(false)
  }

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-30" onClick={onClose} />
      {/* Popover */}
      <div className="fixed z-40 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-2xl border border-gray-200 shadow-xl p-5 w-80">
        <p className="text-sm font-semibold text-gray-900 mb-3">New event</p>
        <input
          autoFocus
          type="text"
          placeholder="Event title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSave()}
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-emerald-400 mb-2"
        />
        <div className="flex gap-2 mb-3">
          <div className="flex-1">
            <label className="text-[10px] font-medium text-gray-400 uppercase tracking-wide">Start</label>
            <input
              type="datetime-local"
              value={startVal}
              onChange={(e) => setStartVal(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-xs outline-none focus:border-emerald-400 mt-0.5"
            />
          </div>
          <div className="flex-1">
            <label className="text-[10px] font-medium text-gray-400 uppercase tracking-wide">End</label>
            <input
              type="datetime-local"
              value={endVal}
              onChange={(e) => setEndVal(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-xs outline-none focus:border-emerald-400 mt-0.5"
            />
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 rounded-lg">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !title.trim()}
            className="px-3 py-1.5 text-xs bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </>
  )
}

// ─── Drag ghost overlay ───────────────────────────────────────────────────────

interface DragState {
  block: Block
  offsetY: number       // px offset within the tile where drag started
  currentY: number      // current mouse Y relative to viewport
  columnEl: HTMLElement | null
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function CalendarPage() {
  const { blocks, loading, refresh, rebuildAndRefresh } = useSchedule()
  const [view, setView] = useState<View>("day")
  const [anchor, setAnchor] = useState(startOfDay(new Date()))
  const [createSlot, setCreateSlot] = useState<{ day: Date; minsFromStart: number } | null>(null)
  const [drag, setDrag] = useState<DragState | null>(null)
  const [rebuilding, setRebuilding] = useState(false)
  const gridRef = useRef<HTMLDivElement>(null)

  // Navigation
  function nav(dir: 1 | -1) {
    setAnchor((prev) => {
      if (view === "day") return addDays(prev, dir)
      if (view === "week") return addDays(prev, dir * 7)
      const d = new Date(prev)
      d.setMonth(d.getMonth() + dir)
      return startOfDay(d)
    })
  }

  // Days in view
  let days: Date[] = []
  if (view === "day") {
    days = [anchor]
  } else if (view === "week") {
    const sunday = addDays(anchor, -anchor.getDay())
    days = Array.from({ length: 7 }, (_, i) => addDays(sunday, i))
  }

  // Filter blocks to current view window
  const visibleBlocks = blocks.filter((b) => {
    const d = parseLocal(b.start_time)
    if (view === "day") return sameDay(d, anchor)
    if (view === "week") return days.some((day) => sameDay(d, day))
    return d.getMonth() === anchor.getMonth() && d.getFullYear() === anchor.getFullYear()
  })

  // Header label
  let headerLabel = ""
  if (view === "day") headerLabel = anchor.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })
  else if (view === "week") headerLabel = `${fmtMonthDay(days[0])} – ${fmtMonthDay(days[6])}`
  else headerLabel = anchor.toLocaleDateString("en-US", { month: "long", year: "numeric" })

  // Click-to-create handler
  function handleClickSlot(day: Date, minsFromStart: number) {
    setCreateSlot({ day, minsFromStart })
  }

  async function handleCreateEvent(title: string, startUtc: string, endUtc: string) {
    await api.createCalendarEvent({ title, start_time: startUtc, end_time: endUtc })
    setCreateSlot(null)
    await refresh()
  }

  // Drag-to-reschedule handlers
  function handleDragStart(block: Block, offsetY: number) {
    setDrag({ block, offsetY, currentY: 0, columnEl: null })

    function onMouseMove(e: MouseEvent) {
      setDrag((prev) => prev ? { ...prev, currentY: e.clientY } : null)
    }

    async function onMouseUp(e: MouseEvent) {
      window.removeEventListener("mousemove", onMouseMove)
      window.removeEventListener("mouseup", onMouseUp)

      setDrag((d) => {
        if (!d || !gridRef.current) return null
        const gridRect = gridRef.current.getBoundingClientRect()
        const relY = e.clientY - gridRect.top - d.offsetY
        const rawMins = (relY / HOUR_PX) * 60
        const snappedMins = snapToInterval(Math.max(0, Math.round(rawMins)), SNAP_MINS)
        const origStart = parseLocal(d.block.start_time)
        const origEnd = parseLocal(d.block.end_time)
        const durMins = (origEnd.getTime() - origStart.getTime()) / 60000

        const newStart = new Date(anchor)
        newStart.setHours(HOUR_START, 0, 0, 0)
        newStart.setMinutes(snappedMins)
        const newEnd = new Date(newStart.getTime() + durMins * 60000)

        const startUtc = newStart.toISOString()
        const endUtc = newEnd.toISOString()

        if (d.block.entry_type === "event") {
          const eventId = d.block.id.replace("event-", "")
          api.updateCalendarEvent(eventId, {
            title: d.block.task_title,
            start_time: startUtc,
            end_time: endUtc,
          }).then(() => refresh())
        } else {
          // Task block — patch task and rebuild schedule
          api.updateTask(d.block.id, { scheduled_time: startUtc }).then(() => rebuildAndRefresh())
        }
        return null
      })
    }

    window.addEventListener("mousemove", onMouseMove)
    window.addEventListener("mouseup", onMouseUp)
  }

  async function handleRebuild() {
    setRebuilding(true)
    await rebuildAndRefresh()
    setRebuilding(false)
  }

  return (
    <AppLayout>
      <div className="flex-1 flex flex-col min-h-0 px-4 md:px-6 py-6 pb-24 md:pb-6 gap-4">
        {/* Toolbar */}
        <div className="flex items-center justify-between gap-4 flex-wrap shrink-0">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setAnchor(startOfDay(new Date()))}
              className="text-xs px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-lg transition text-gray-600 font-medium"
            >
              Today
            </button>
            <button onClick={() => nav(-1)} className="text-gray-400 hover:text-gray-700 px-2 text-lg leading-none">‹</button>
            <button onClick={() => nav(1)} className="text-gray-400 hover:text-gray-700 px-2 text-lg leading-none">›</button>
            <span className="text-sm font-semibold text-gray-900">{headerLabel}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCreateSlot({ day: anchor, minsFromStart: 9 * 60 - HOUR_START * 60 })}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium transition"
            >
              <Plus className="h-3.5 w-3.5" />
              Add event
            </button>
            <button
              onClick={handleRebuild}
              disabled={rebuilding}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-600 font-medium transition disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${rebuilding ? "animate-spin" : ""}`} />
              Sync schedule
            </button>
            <div className="flex gap-1 bg-gray-100 rounded-xl p-1 text-xs">
              {(["day", "week", "month"] as View[]).map((v) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  className={`px-3 py-1.5 rounded-lg capitalize transition font-medium ${
                    view === v ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Calendar grid */}
        <div ref={gridRef} className="flex-1 min-h-0 bg-white border border-gray-200 rounded-2xl overflow-hidden">
          {loading ? (
            <div className="h-full flex items-center justify-center text-sm text-gray-400">Loading…</div>
          ) : view === "month" ? (
            <MonthGrid
              anchor={anchor}
              blocks={visibleBlocks}
              onDayClick={(day) => { setAnchor(day); setView("day") }}
            />
          ) : (
            <TimeGrid
              days={days}
              blocks={visibleBlocks}
              onClickSlot={handleClickSlot}
              onDragStart={handleDragStart}
            />
          )}
        </div>
      </div>

      {/* Create event popover */}
      {createSlot && (
        <CreatePopover
          initialDay={createSlot.day}
          initialMinsFromStart={createSlot.minsFromStart}
          onSave={handleCreateEvent}
          onClose={() => setCreateSlot(null)}
        />
      )}
    </AppLayout>
  )
}
```

**Step 2: Add `updateCalendarEvent` to the API client**

In `frontend/src/lib/api.ts`, add inside the `api` object:

```ts
updateCalendarEvent: (id: string, data: object) =>
  authFetch(`/api/calendar/events/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
```

**Step 3: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep error | head -20
```

Fix any type errors before continuing.

**Step 4: Run build**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully`

**Step 5: Commit**

```bash
git add frontend/src/app/calendar/page.tsx frontend/src/lib/api.ts
git commit -m "feat(calendar): full Google Calendar-style rewrite — proportional tiles, drag-to-reschedule, click-to-create, sync button"
```

---

### Task 6: Frontend — Wire matrix moves to rebuildAndRefresh

When a task bubble is dragged to a new quadrant on the matrix, the schedule should rebuild silently and the calendar should update.

**Files:**
- Modify: `frontend/src/app/matrix/page.tsx`

**Step 1: Replace the local fetch with `useSchedule` and add rebuild trigger**

In `frontend/src/app/matrix/page.tsx`, make these changes:

1. Add import at the top:
```ts
import { useSchedule } from "@/lib/schedule-store"
```

2. Inside `MatrixPage`, add:
```ts
const { rebuildAndRefresh } = useSchedule()
```

3. In `persistTask`, after the `api.updateTask` call resolves, trigger rebuild:

Replace the current `persistTask` function with:

```ts
async function persistTask(
  taskId: string,
  payload: Record<string, unknown>,
  optimistic: Partial<MappedTask>
) {
  setTasks((prev) => mergeTask(prev, taskId, optimistic));
  try {
    const saved = await api.updateTask(taskId, payload);
    setTasks((prev) =>
      prev.map((task) =>
        task.id === taskId ? mapApiTaskToMatrixTask(saved as Record<string, unknown>) : task
      )
    );
    // Rebuild schedule silently — matrix moves change priority, which changes scheduling order
    rebuildAndRefresh().catch(() => {});
  } catch {
    // Keep optimistic state.
  }
}
```

**Step 2: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "matrix" | head -10
```

Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/src/app/matrix/page.tsx
git commit -m "feat(matrix): trigger schedule rebuild after task move — matrix→schedule→calendar chain complete"
```

---

### Task 7: Verification

**Step 1: Run all backend tests**

```bash
cd backend && pytest -v 2>&1 | tail -30
```

Expected: all tests pass, including `test_schedule_respects_user_timezone`.

**Step 2: Run frontend tests**

```bash
cd frontend && node --test src/lib/calendar-utils.test.ts && node --test src/app/dashboard/dashboard-state.test.ts
```

Expected: all tests pass.

**Step 3: Run full frontend build**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully`

**Step 4: Manual smoke test — start dev server**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000/calendar` and verify:
- Day view: hour grid visible (7am–11pm), scrollable
- Events render with correct height proportional to duration
- Clicking an empty time slot opens the "New event" popover with time pre-filled
- Saving a 9pm event shows it at 9pm (not a shifted time)
- "Sync schedule" button triggers a rebuild and the grid refreshes
- Dragging an event tile to a new time updates it
- Clicking a day cell in month view navigates to that day in day view

Open `http://localhost:3000/matrix` and verify:
- Dragging a task bubble to a new quadrant triggers a background schedule rebuild
- Navigating to Calendar afterwards shows the updated block positions

**Step 5: Final commit if any polish tweaks were made**

```bash
git add -p
git commit -m "fix(calendar): post-smoke-test polish"
```
