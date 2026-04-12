# Skip & Reschedule Design

**Date:** 2026-04-12  
**Status:** Approved

---

## Problem

The `HeroTaskCard` only offers "Mark Complete" and "Edit." Users have no way to act on a task they can't or won't do right now. Two distinct actions are needed:

- **Skip** — I'm not doing this at all, remove it permanently. Keep the deadline on the calendar.
- **Reschedule** — I'll do it later. Snooze it without touching the deadline; it resurfaces daily until the deadline passes.

---

## Decisions

| Question | Decision |
|---|---|
| Where do buttons live? | `HeroTaskCard` only (primary task) |
| Skip persistence | Permanent delete — task is gone, GCal event preserved |
| Reschedule mechanism | `snoozed_until` date on task, not a deadline change |
| Reschedule options | Tomorrow / In 2 days / Next week |
| After deadline passes | Rescheduled tasks auto-expire (filtered from all active views) |
| Skip re-scheduling prevention | Set `snoozed_until = today` before delete to prevent race with scheduler |

---

## Backend

### Task model
Add one nullable column:
```
snoozed_until: Date (nullable)
```
Alembic migration required.

### New endpoint
```
POST /api/tasks/{id}/snooze
Body: { days: 1 | 2 | 7 }
Effect: snoozed_until = today + days
```
No change to task status or deadline.

### Skip
Reuse existing `DELETE /api/tasks/{id}`. No new endpoint.  
Current behavior already: deletes Task row + ScheduleBlock rows, never touches Google Calendar events.

### Query filter changes
Two new exclusion rules applied in both `get_today` and `schedule_runner`:
1. Exclude tasks where `snoozed_until > today`
2. Exclude tasks where `deadline < today` (deadline has passed, task not completed)

Rule 2 is the auto-expiry for overdue rescheduled tasks — they silently fall off without a hard delete.

---

## Frontend

### `api.ts`
```ts
snoozeTask: (id: string, days: 1 | 2 | 7) =>
  authFetch(`/api/tasks/${id}/snooze`, { method: "POST", body: JSON.stringify({ days }) })
```

### `HeroTaskCard`
Add two buttons to the actions row:

**Skip**
- One click, no confirmation
- Calls `deleteTask(id)` 
- Removes task from local state immediately (optimistic)
- Dashboard refreshes to show next primary task

**Reschedule**
- Opens a small inline popover
- Three preset buttons: Tomorrow / In 2 days / Next week
- Clicking a preset calls `snoozeTask(id, days)`, closes popover, refreshes dashboard
- Next highest-priority unsnoozed task becomes the new hero

### `types/index.ts`
Add `snoozed_until: string | null` to `Task` interface and `mapApiTask`.

### `SecondaryTasks`
No changes.

---

## State transitions

```
pending/scheduled
  → [Skip]       → DELETED (GCal event preserved)
  → [Reschedule] → snoozed_until set, status unchanged
                    resurfaces each day until deadline
                    after deadline: auto-filtered from all views
  → [Complete]   → completed (existing)
```

---

## Out of scope

- Custom date picker for snooze (YAGNI — 3 presets cover 95% of cases)
- Skip/reschedule on secondary task rows
- Hard-deleting expired tasks (filtering is sufficient; hard delete is a separate cleanup job)
- Auto-marking overdue tasks as `missed` (separate feature)
