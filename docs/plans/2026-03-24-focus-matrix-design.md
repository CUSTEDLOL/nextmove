# Focus Matrix Redesign — Design Document

_Approved: 2026-03-24_

## Goal

Completely rewrite the `/matrix` page and its three component files (`MatrixCanvas.tsx`, `DraggableBubble.tsx`, `page.tsx`) to produce a clean, production-quality Focus Matrix that looks great on both desktop and mobile. The existing Codex-generated implementation is replaced in full.

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| Grid model | 4-quadrant Eisenhower (Q1–Q4) | Simpler, universally understood, cleaner visual than K-Timesaver sub-cells |
| Mobile interaction | Tap-to-assign bottom sheet | Drag-and-drop is fiddly on small screens; bottom sheet is reliable and easy |
| Desktop interaction | Drag-and-drop (framer-motion) | Preserved from original design |
| Data | Hardcoded mock | API wiring is a follow-up; visual design must not be blocked on backend |

## Page Layout

The page lives inside `AppLayout`. Layout stacks vertically on mobile, side-by-side on desktop (md+).

**Header:**
- Heading: "Map your work into the quadrants that matter."
- Subtitle: one-line axis explanation
- Two stat pills: "Scheduled today" count + "Top focus" task name
- On mobile: stats go full-width below the heading, no side-by-side arrangement

**Canvas:**
- Desktop: full-width, `min-h-[640px]`
- Mobile: `min-h-[420px]`, same canvas scaled down, tap interaction replaces drag

## Matrix Visual Design

**Quadrant backgrounds** — four clean solid-tint divs, one per quadrant. No overlapping radial gradients:
- Q1 top-right (Do First): `bg-emerald-50/80`
- Q2 top-left (Plan): `bg-slate-50/60`
- Q3 bottom-left (Backlog): white
- Q4 bottom-right (Delegate): white

**Dividers:** two straight solid lines, `1.5px`, `border-gray-200`. Drawn as absolute divs (not SVG), centered horizontally and vertically.

**Axis labels:**
- "IMPORTANCE" rotated 90° on the left edge, small, `tracking-widest`, `text-gray-400`
- "URGENCY" along the bottom-right, same treatment

**Quadrant labels:** pill badges in each corner:
- Q1 Do First — emerald text + emerald border
- Q2 Plan, Q3 Backlog, Q4 Delegate — slate/gray

**Removed from Codex implementation:**
- Critical-path SVG overlay (reads as noise)
- Six overlapping radial gradient background divs
- Dashed SVG divider lines
- "Main Task Quadrant" / "Backlog Pool" floating badges (replaced by corner labels)

## Task Bubbles

**Sizing formula:** `size = 80 + (priorityScore / 100) * 60` → range 80–140px. Tighter than the previous 76–154px range to reduce crowding.

**Scheduled today:** emerald ring + white fill + soft emerald drop shadow + "Today" badge inside

**Not scheduled:** white fill + `border-gray-200` + lighter shadow

**Top priority task only:** subtle emerald pulse glow (`animate-pulse` on a blurred div behind the bubble)

**Inside each bubble:** title (2-line clamp, size-responsive font), effort zap icons, "Today" badge if scheduled

**Idle animation:** slow floating `y: [0, -4, 0]` at 7s duration (slowed from current 5.5s to reduce jitter)

**On mobile:** bubbles respond to tap, not drag. `onTap` triggers the bottom sheet.

## Mobile Bottom Sheet (`BubbleSheet.tsx`)

A new component. Renders only when a bubble is tapped on screens `≤768px`.

**Structure:**
- Dark overlay behind the sheet (`bg-black/40`, dismisses on tap)
- Sheet slides up from bottom with `framer-motion` `y` animation
- Task title shown at top of sheet
- Four large tap targets, one per quadrant, with icon and label:
  - Q1 Do First (emerald)
  - Q2 Plan (slate)
  - Q3 Backlog (gray)
  - Q4 Delegate (gray)
- Tapping a quadrant calls `onMoveTask(taskId, quadrant)`, closes the sheet
- Swipe-down gesture dismisses (framer-motion drag on y-axis)

**Desktop:** `BubbleSheet` is never mounted. `onTap` is not wired on desktop.

## Component Files

| File | Role |
|---|---|
| `frontend/src/app/matrix/page.tsx` | Page shell, mock data state, header, stats, passes tasks to canvas |
| `frontend/src/components/matrix/MatrixCanvas.tsx` | Matrix board, quadrant backgrounds, dividers, axis labels, bubble placement |
| `frontend/src/components/matrix/DraggableBubble.tsx` | Bubble rendering, drag (desktop), tap (mobile), idle animation |
| `frontend/src/components/matrix/BubbleSheet.tsx` | Mobile bottom sheet for quadrant assignment |
| `frontend/src/components/matrix/types.ts` | Shared types — updated to include `quadrant` field |

## Updated Data Model

```ts
export type MappedTask = {
  id: string;
  title: string;
  urgency: number;       // 0–100
  importance: number;    // 0–100
  priorityScore: number; // 0–100
  effort: 1 | 2 | 3;
  scheduledToday: boolean;
  quadrant: "Q1" | "Q2" | "Q3" | "Q4"; // derived, but overridable by drag/tap
};
```

## Interaction Rules

**Desktop:**
- Drag a bubble into Q1 (top-right) → marks it `scheduledToday: true`, updates `quadrant: "Q1"`
- Dragging into any other quadrant updates `quadrant` accordingly
- Bubble snaps back if dropped outside the board

**Mobile:**
- Tap a bubble → bottom sheet opens
- Tap a quadrant in the sheet → `quadrant` updated, `scheduledToday` set to `true` if Q1
- Sheet closes with animation

## Deferred Work

- Live API-backed task loading and persistence
- Collision avoidance / force-directed layout
- Opening/editing a task from the matrix
- Mobile bottom tab bar entry for `/matrix`
- Pinch-to-zoom on the mobile canvas
