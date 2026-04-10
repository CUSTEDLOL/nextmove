# Calendar Redesign + Brain Dump Sync — Design Doc

**Approved:** Approach A — vivid solid tiles, white text, high contrast grid

---

## Problem

1. **Unreadable calendar** — tiles use `bg-blue-50` / `bg-red-50` (near-white), text is 10–11px, grid lines are `gray-100` (invisible). Result: no contrast, nothing stands out.
2. **Modal overflow** — `CreatePopover` has no max-height or scroll, breaks on small screens.
3. **Calendar doesn't update after brain dump** — `refreshDashboard()` re-fetches task list but never calls `rebuildAndRefresh()`, so new tasks never land in the schedule or calendar.

---

## Design Decisions

### 1. Visual: Vivid Solid Tiles (Approach A)

| Element | Before | After |
|---|---|---|
| Task block | `bg-blue-50 text-blue-900` | `bg-blue-600 text-white` |
| Deadline | `bg-red-50 text-red-800` | `bg-red-600 text-white` |
| Event | `bg-amber-50 text-amber-900` | `bg-amber-500 text-white` |
| Prep | `bg-gray-50 text-gray-500 border-dashed` | `bg-gray-400 text-white border-dashed` |
| Tile font | `text-[10px]` / `text-[11px]` | `text-xs` (12px) / `text-[11px]` short |
| Tile min-height | 24px | 28px |
| Left accent bar | `border-l-[3px]` same hue | removed (redundant with full color) |
| Grid hour lines | `border-gray-100` | `border-gray-200` |
| Half-hour lines | `border-gray-50` | `border-gray-100` |
| Hour labels | `text-[10px] text-gray-400` | `text-xs text-gray-500 font-medium` |
| Day headers | plain text | bold, today = `bg-blue-600 text-white` pill |
| HOUR_PX | 60 | 72 (more vertical breathing room) |
| Now indicator | `bg-emerald-500` | keep, but dot enlarged to `w-3 h-3` |

Hover: darken tile by one step (`hover:brightness-90`). Active drag: `opacity-75 scale-[0.98]`.

### 2. Modal Overflow Fix

`CreatePopover` gets `max-h-[90dvh] overflow-y-auto` and `w-[min(20rem,90vw)]` so it never overflows on small screens or when the soft keyboard appears.

### 3. Brain Dump → Calendar Sync Fix

**Root cause:** `DashboardPage.handleBrainDump` calls `api.brainDump()` then `refreshDashboard()` (which only re-fetches the task list), but never rebuilds the schedule.

**Fix:** Restructure `DashboardPage` the same way `CalendarPage` was fixed — extract an inner `DashboardContent` component rendered inside `<AppLayout>`, so it can call `useSchedule()` correctly. After a successful brain dump, call `rebuildAndRefresh()` from the schedule store. This rebuilds the schedule, updates the shared `ScheduleProvider` state, and the calendar reflects it immediately without a page reload.

---

## What Is NOT Changing

- Layout structure (gutter + scrollable day columns)
- Drag-to-reschedule logic
- Month view (inherits color fixes from `BLOCK_COLORS`)
- Backend — purely frontend change
