# Calendar Redesign + Brain Dump Sync — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the calendar visually bold and readable (vivid full-color tiles, higher contrast grid), fix modal overflow, and ensure the calendar updates immediately after a brain dump.

**Architecture:** Three isolated frontend-only changes to `calendar/page.tsx` and `dashboard/page.tsx`. No backend changes. No new dependencies. Brain dump sync uses the existing `ScheduleProvider` / `rebuildAndRefresh` pattern already established for the matrix page.

**Tech Stack:** Next.js 14 App Router, TypeScript, Tailwind CSS, existing `useSchedule` hook from `src/lib/schedule-store.tsx`

---

### Task 1: Calendar — Vivid tile colors + higher-contrast grid

**Files:**
- Modify: `frontend/src/app/calendar/page.tsx`

**Step 1: Update `BLOCK_COLORS`, `BLOCK_ACCENT`, and `HOUR_PX`**

Replace the constants block (lines ~26–46) with:

```tsx
const HOUR_PX = 72
const HOUR_START = 7
const HOUR_END = 23
const TOTAL_HOURS = HOUR_END - HOUR_START
const SNAP_MINS = 15

const BLOCK_COLORS: Record<Block["entry_type"], string> = {
  block:    "bg-blue-600 text-white",
  deadline: "bg-red-600 text-white",
  prep:     "bg-gray-400 text-white border-dashed",
  event:    "bg-amber-500 text-white",
}

const BLOCK_ACCENT: Record<Block["entry_type"], string> = {
  block:    "bg-blue-400",
  deadline: "bg-red-400",
  prep:     "bg-gray-300",
  event:    "bg-amber-300",
}
```

**Step 2: Update `EventTile` — remove left accent bar, increase min-height, fix font sizes, add hover/drag feedback**

Replace the `EventTile` return JSX with:

```tsx
  return (
    <div
      className={`absolute rounded-lg overflow-hidden cursor-grab active:cursor-grabbing select-none hover:brightness-90 transition-all ${BLOCK_COLORS[block.entry_type]}`}
      style={{
        top: topPx,
        height: heightPx,
        left: `${col * colW + 0.5}%`,
        width: `${colW - 1}%`,
        zIndex: 10,
        minHeight: 28,
      }}
      onMouseDown={(e) => {
        e.stopPropagation()
        const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
        onDragStart(block, e.clientY - rect.top)
      }}
    >
      <div className="px-2 py-1 h-full flex flex-col justify-start overflow-hidden">
        <p className={`font-semibold leading-tight truncate ${isShort ? "text-[11px]" : "text-xs"}`}>
          {block.task_title}
        </p>
        {!isShort && (
          <p className="text-[10px] opacity-75 mt-0.5">
            {fmtTime(start)} – {fmtTime(end)}
          </p>
        )}
      </div>
    </div>
  )
```

**Step 3: Update `TimeGrid` — bolder hour labels, more visible grid lines, larger now-indicator dot, bold day headers**

In the gutter section, replace the hour label span:
```tsx
<span className="text-xs font-medium text-gray-500">{fmtHour(HOUR_START + i)}</span>
```

Replace the hour line divs:
```tsx
{/* Hour lines */}
{Array.from({ length: TOTAL_HOURS }, (_, i) => (
  <div
    key={i}
    className="absolute w-full border-t border-gray-200"
    style={{ top: i * HOUR_PX }}
  />
))}
{/* 30-min sub-lines */}
{Array.from({ length: TOTAL_HOURS }, (_, i) => (
  <div
    key={`half-${i}`}
    className="absolute w-full border-t border-gray-100"
    style={{ top: i * HOUR_PX + HOUR_PX / 2 }}
  />
))}
```

Replace the now-indicator:
```tsx
{isToday && isNowVisible && (
  <div
    className="absolute w-full z-20 flex items-center pointer-events-none"
    style={{ top: nowPx }}
  >
    <div className="w-3 h-3 rounded-full bg-emerald-500 -ml-1.5 shrink-0" />
    <div className="flex-1 h-[2px] bg-emerald-500" />
  </div>
)}
```

Replace the day header pill in the sticky header:
```tsx
<span
  className={`text-xs font-bold px-2.5 py-1 rounded-full ${
    isToday ? "bg-blue-600 text-white" : "text-gray-600"
  }`}
>
  {day.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
</span>
```

**Step 4: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -v "test.ts" | grep error | head -10
```

Expected: no errors.

**Step 5: Run build**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: `✓ Compiled successfully`

**Step 6: Commit**

```bash
git add src/app/calendar/page.tsx
git commit -m "feat(calendar): vivid tile colors, higher-contrast grid, bolder labels"
```

---

### Task 2: Calendar — Fix `CreatePopover` modal overflow

**Files:**
- Modify: `frontend/src/app/calendar/page.tsx` — `CreatePopover` component

**Step 1: Add max-height + responsive width to the popover container**

Find the popover `<div>` with class `fixed z-40 top-1/2 left-1/2 ...` and replace:

```tsx
<div className="fixed z-40 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-2xl border border-gray-200 shadow-xl p-5 w-80">
```

With:

```tsx
<div className="fixed z-40 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-2xl border border-gray-200 shadow-xl p-5 w-[min(20rem,90vw)] max-h-[90dvh] overflow-y-auto">
```

**Step 2: Run build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: `✓ Compiled successfully`

**Step 3: Commit**

```bash
git add src/app/calendar/page.tsx
git commit -m "fix(calendar): prevent CreatePopover overflow on small screens"
```

---

### Task 3: Dashboard — Wire brain dump to `rebuildAndRefresh`

When a brain dump creates new tasks, the schedule must be rebuilt so the calendar reflects them immediately.

**Root cause:** `DashboardPage.handleDump` (line 129) calls `api.brainDump()` then `refreshDashboard()` but never `rebuildAndRefresh()`. Additionally, `DashboardPage` calls no hook at top-level, but to add `useSchedule()` we must apply the same fix as `CalendarPage` — extract an inner `DashboardContent` component rendered inside `<AppLayout>` so it is a descendant of `ScheduleProvider`.

**Files:**
- Modify: `frontend/src/app/dashboard/page.tsx`

**Step 1: Add `useSchedule` import**

At the top of the file, add:

```tsx
import { useSchedule } from "@/lib/schedule-store";
```

**Step 2: Extract `DashboardContent` and wire `rebuildAndRefresh`**

Rename `DashboardPage` to `DashboardContent` (remove the `export default`), then add a new thin default export at the bottom:

```tsx
export default function DashboardPage() {
  return (
    <AppLayout>
      <DashboardContent />
    </AppLayout>
  );
}
```

Inside `DashboardContent` (formerly `DashboardPage`):

1. Remove `<AppLayout>` wrapper from its return — replace with `<>` fragment.

2. Add at the top of the function body (alongside the other `useState` calls):
```tsx
const { rebuildAndRefresh } = useSchedule();
```

3. Replace `handleDump`:
```tsx
async function handleDump(text: string) {
  const data = await api.brainDump(text) as { tasks?: Array<Record<string, unknown>> };
  // Rebuild schedule so new tasks land in calendar immediately
  rebuildAndRefresh().catch(() => {});
  try {
    await refreshDashboard();
  } catch {
    // Keep the optimistic confirmation even if the follow-up refresh fails.
  }
  const titles = (data.tasks ?? []).map((task) => String(task.title ?? "Untitled task"));
  return {
    createdCount: titles.length,
    titles,
  };
}
```

**Step 3: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -v "test.ts" | grep error | head -10
```

Expected: no errors.

**Step 4: Run build**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: `✓ Compiled successfully`

**Step 5: Commit**

```bash
git add src/app/dashboard/page.tsx
git commit -m "fix(dashboard): trigger schedule rebuild after brain dump — calendar updates immediately"
```

---

### Task 4: Verification

**Step 1: Run frontend tests**

```bash
cd frontend && node --test src/lib/calendar-utils.test.ts && node --test src/app/dashboard/dashboard-state.test.ts
```

Expected: all tests pass.

**Step 2: Run full frontend build**

```bash
cd frontend && npm run build 2>&1 | tail -15
```

Expected: `✓ Compiled successfully`

**Step 3: Run backend tests (sanity check — no backend changes, should be clean)**

```bash
cd backend && pytest tests/test_calendar_api.py tests/test_schedule_api.py -v 2>&1 | tail -15
```

Expected: all pass.
