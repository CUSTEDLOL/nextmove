# Focus Matrix V2 — Design Document

_Approved: 2026-03-24_

## Goal

Redesign the `/matrix` page visual layer: replace circular bubbles with rectangular tiles, introduce soft tonal quadrant backgrounds with large ghost typography, and replace Zap effort icons with a Low/Med/High pill label. Overall direction: professional, sleek, bold-but-calm.

## Design Direction

**Soft Tonal + Bold Typography** — off-white board base, barely-perceptible per-quadrant tints, large ghost watermark text giving each quadrant spatial identity, clean white tiles with colored left-border accents.

## Board & Quadrants

**Board:** `bg-[#FAFAFA]` base, `rounded-2xl`, subtle outer shadow, `border border-gray-200`.

**Per-quadrant backgrounds** — two layers each:
1. Soft tint (`~50-60% opacity`):
   - Q1 Do First: `bg-emerald-50/60`
   - Q2 Plan: `bg-blue-50/50`
   - Q3 Backlog: `bg-slate-50/40`
   - Q4 Delegate: `bg-amber-50/40`
2. Ghost watermark word centered in each quadrant — uppercase, `font-black`, `text-[80px] md:text-[96px]`, `opacity-[0.04]`, `select-none pointer-events-none`, text:
   - Q1: "DO FIRST"
   - Q2: "PLAN"
   - Q3: "BACKLOG"
   - Q4: "DELEGATE"

**Dividers:** Two absolute divs — `w-px bg-gray-200` (vertical) and `h-px bg-gray-200` (horizontal).

**Corner labels:** Small pill — colored left dot + bold text. e.g. `● Q1 · Do First`. Emerald for Q1, blue for Q2, slate for Q3, amber for Q4.

**Axis labels:** "IMPORTANCE" (rotated left) and "URGENCY" (bottom right). `text-[10px] tracking-[0.3em] text-gray-300`.

## Tile Design

**Shape:** `rounded-xl`, fixed `w-[152px]`, `min-h-[80px]`, white `bg-white`, `border border-gray-200`, `shadow-sm`. Positioned absolutely by urgency/importance coordinates.

**Left border accent:** `border-l-2` in quadrant color:
- Q1: `border-l-emerald-400`
- Q2: `border-l-blue-400`
- Q3: `border-l-slate-300`
- Q4: `border-l-amber-400`

**Inside each tile (top to bottom):**
- Task title: `text-sm font-semibold text-gray-900`, 2-line clamp
- Row with effort pill + "Today" badge (if scheduled):
  - Effort pill: `text-[10px] font-medium rounded-full px-2 py-0.5` — muted bg
    - Low (effort 1): `bg-slate-100 text-slate-500`
    - Med (effort 2): `bg-amber-50 text-amber-600`
    - High (effort 3): `bg-rose-50 text-rose-500`
  - Today badge: small `bg-emerald-100 text-emerald-700` pill (only if `scheduledToday`)

**Hover:** `shadow-md -translate-y-0.5 transition-all`

**Drag:** `shadow-xl rotate-1 opacity-90 scale-[1.02]`

**Top priority tile only:** subtle `ring-2 ring-emerald-300/50` glow

**No size variation** — all tiles same `w-[152px]`. Height grows with content.

## Removing Variable Bubble Sizing

`bubbleSize()` function removed. All tiles render at fixed width. Priority is communicated through position (top-right = Q1) and the left-border accent color.

## Effort Mapping

```ts
function effortLabel(effort: 1 | 2 | 3): "Low" | "Med" | "High" {
  return effort === 1 ? "Low" : effort === 2 ? "Med" : "High";
}
```

## Mobile Bottom Sheet

Restyled to match new palette:
- Sheet bg: `bg-[#FAFAFA]`
- Each quadrant option shows ghost word + soft tint bg
- Same spring animation, swipe-to-dismiss, ring colors

## Drag Behavior

Dragging a tile to a new quadrant:
- Updates `quadrant` and `scheduledToday` (Q1 = today)
- Tile left-border color updates to match new quadrant
- Ghost watermark in destination quadrant remains static

## Files Changed

| File | Change |
|---|---|
| `frontend/src/components/matrix/MatrixCanvas.tsx` | Replace quadrant backgrounds with tonal tints + ghost words; update tile placement |
| `frontend/src/components/matrix/DraggableBubble.tsx` | Replace circular bubble with rectangular tile; add effortLabel; remove bubbleSize |
| `frontend/src/components/matrix/BubbleSheet.tsx` | Restyle to match tonal palette |
| `frontend/src/app/matrix/page.tsx` | Minor: remove `bubbleSize` import if any |

## What's Not Changing

- `types.ts` — no changes needed
- Drag logic (`quadrantFromPosition`, `onMoveTask`, `onTap`) — unchanged
- `useIsMobile`, `ResizeObserver`, `taskToPoint` — unchanged
- Mock data — unchanged
