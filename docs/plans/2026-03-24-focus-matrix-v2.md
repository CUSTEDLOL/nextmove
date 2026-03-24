# Focus Matrix V2 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace circular bubbles with rectangular tiles, add soft tonal quadrant backgrounds with ghost watermark typography, and swap Zap icons for Low/Med/High effort pills.

**Architecture:** Visual-only rewrite of three component files plus a types.ts cleanup. Drag logic, mobile sheet, mock data, and coordinate mapping are all unchanged. The `size` prop is removed from `DraggableBubbleProps` since tiles have a fixed width. MatrixCanvas passes center coordinates (`x`, `y`) directly to DraggableBubble.

**Tech Stack:** Next.js 14, TypeScript, Tailwind CSS, framer-motion, lucide-react (removed from DraggableBubble)

---

### Task 1: Remove `size` from types.ts

**Files:**
- Modify: `frontend/src/components/matrix/types.ts`

**Step 1: Remove the `size` field from `DraggableBubbleProps`**

Replace the entire file with:

```ts
export type Quadrant = "Q1" | "Q2" | "Q3" | "Q4";

export type MappedTask = {
  id: string;
  title: string;
  urgency: number;       // 0–100, higher = more urgent
  importance: number;    // 0–100, higher = more important
  priorityScore: number; // 0–100
  effort: 1 | 2 | 3;
  scheduledToday: boolean;
  quadrant: Quadrant;
};

export type MatrixCanvasProps = {
  tasks: MappedTask[];
  onMoveTask: (taskId: string, quadrant: Quadrant) => void;
};

export type DraggableBubbleProps = {
  task: MappedTask;
  left: number;           // center x coordinate on the board
  top: number;            // center y coordinate on the board
  containerWidth: number;
  containerHeight: number;
  verticalDividerX: number;
  horizontalDividerY: number;
  isCritical: boolean;
  isMobile: boolean;
  onMoveTask: (taskId: string, quadrant: Quadrant) => void;
  onTap: (taskId: string) => void;
};

export type BubbleSheetProps = {
  task: MappedTask | null;
  onMove: (quadrant: Quadrant) => void;
  onDismiss: () => void;
};
```

**Step 2: Verify — errors are expected in DraggableBubble/MatrixCanvas until Tasks 2-3 are done**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "matrix/types"
```

Expected: no errors inside `types.ts` itself

**Step 3: Commit**

```bash
cd frontend && git add src/components/matrix/types.ts
git commit -m "feat(matrix-v2): remove size prop from DraggableBubbleProps — tiles use fixed width"
```

---

### Task 2: Rewrite DraggableBubble.tsx — rectangular tile

**Files:**
- Modify: `frontend/src/components/matrix/DraggableBubble.tsx`

**Step 1: Replace the entire file**

```tsx
"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { DraggableBubbleProps, Quadrant } from "@/components/matrix/types";

const TILE_W = 152;
const TILE_H = 80; // used for drag constraint bounds and center offset

function clamp(v: number, min: number, max: number) {
  return Math.min(Math.max(v, min), max);
}

function quadrantFromPosition(
  cx: number,
  cy: number,
  midX: number,
  midY: number
): Quadrant {
  if (cx >= midX && cy < midY) return "Q1";
  if (cx < midX && cy < midY) return "Q2";
  if (cx < midX && cy >= midY) return "Q3";
  return "Q4";
}

function effortLabel(effort: 1 | 2 | 3): "Low" | "Med" | "High" {
  return effort === 1 ? "Low" : effort === 2 ? "Med" : "High";
}

const QUADRANT_ACCENT: Record<Quadrant, string> = {
  Q1: "border-l-emerald-400",
  Q2: "border-l-blue-400",
  Q3: "border-l-slate-300",
  Q4: "border-l-amber-400",
};

const EFFORT_STYLE: Record<"Low" | "Med" | "High", string> = {
  Low:  "bg-slate-100 text-slate-500",
  Med:  "bg-amber-50 text-amber-600",
  High: "bg-rose-50 text-rose-500",
};

export function DraggableBubble({
  task,
  left,
  top,
  containerWidth,
  containerHeight,
  verticalDividerX,
  horizontalDividerY,
  isCritical,
  isMobile,
  onMoveTask,
  onTap,
}: DraggableBubbleProps) {
  const [isDragging, setIsDragging] = useState(false);

  // left/top are center coords — offset to get top-left corner for positioning
  const x = clamp(left - TILE_W / 2, 0, Math.max(containerWidth - TILE_W, 0));
  const y = clamp(top - TILE_H / 2, 0, Math.max(containerHeight - TILE_H, 0));
  const maxLeft = Math.max(containerWidth - TILE_W, 0);
  const maxTop = Math.max(containerHeight - TILE_H, 0);

  const shouldGlow = isCritical && task.scheduledToday;
  const effort = effortLabel(task.effort);
  const accentClass = QUADRANT_ACCENT[task.quadrant];
  const effortStyle = EFFORT_STYLE[effort];

  // tile center for quadrant detection after drag
  const tileCenterX = x + TILE_W / 2;
  const tileCenterY = y + TILE_H / 2;

  return (
    <motion.div
      className="absolute touch-none select-none"
      style={{
        left: x,
        top: y,
        width: TILE_W,
        zIndex: isDragging ? 50 : shouldGlow ? 30 : 10,
      }}
      drag={!isMobile}
      dragElastic={0}
      dragMomentum={false}
      dragConstraints={{
        left: -x,
        right: maxLeft - x,
        top: -y,
        bottom: maxTop - y,
      }}
      onDragStart={() => setIsDragging(true)}
      onDragEnd={(_, info) => {
        setIsDragging(false);
        const finalCX = tileCenterX + info.offset.x;
        const finalCY = tileCenterY + info.offset.y;
        const q = quadrantFromPosition(finalCX, finalCY, verticalDividerX, horizontalDividerY);
        onMoveTask(task.id, q);
      }}
      onTap={() => {
        if (isMobile) onTap(task.id);
      }}
      whileTap={{ scale: isMobile ? 0.95 : 0.98 }}
      animate={
        isDragging
          ? { rotate: 1.5, scale: 1.02 }
          : { rotate: 0, scale: 1 }
      }
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      aria-label={`${task.title}, ${effort} effort, ${task.quadrant}`}
    >
      <div
        className={cn(
          "relative w-full rounded-xl border border-l-2 border-gray-200 bg-white px-3 py-2.5 transition-all duration-150",
          accentClass,
          shouldGlow && "ring-2 ring-emerald-200/70",
          isDragging
            ? "shadow-xl opacity-90"
            : "shadow-sm hover:shadow-md hover:-translate-y-0.5"
        )}
      >
        {/* Title */}
        <p className="line-clamp-2 text-sm font-semibold leading-snug text-gray-900">
          {task.title}
        </p>

        {/* Badges */}
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-[10px] font-medium",
              effortStyle
            )}
          >
            {effort}
          </span>
          {task.scheduledToday && (
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
              Today
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}
```

**Step 2: Commit**

```bash
cd frontend && git add src/components/matrix/DraggableBubble.tsx
git commit -m "feat(matrix-v2): replace bubble with rectangular tile — effort label, quadrant accent border"
```

---

### Task 3: Update MatrixCanvas.tsx — tonal backgrounds + ghost words

**Files:**
- Modify: `frontend/src/components/matrix/MatrixCanvas.tsx`

**Step 1: Replace the entire file**

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { DraggableBubble } from "@/components/matrix/DraggableBubble";
import { BubbleSheet } from "@/components/matrix/BubbleSheet";
import type { MatrixCanvasProps, MappedTask, Quadrant } from "@/components/matrix/types";

const PADDING = 64;
const FALLBACK_W = 1100;
const FALLBACK_H = 680;

function clamp(v: number, lo: number, hi: number) {
  return Math.min(Math.max(v, lo), hi);
}

function taskToPoint(task: MappedTask, w: number, h: number) {
  const usableW = Math.max(w - PADDING * 2, 300);
  const usableH = Math.max(h - PADDING * 2, 300);
  return {
    x: clamp(PADDING + (task.urgency / 100) * usableW, PADDING, w - PADDING),
    y: clamp(PADDING + (1 - task.importance / 100) * usableH, PADDING, h - PADDING),
  };
}

function useIsMobile() {
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const check = () => setMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);
  return mobile;
}

// Grid order: top-left, top-right, bottom-left, bottom-right
const QUADRANTS = [
  { id: "Q2" as Quadrant, label: "Q2 · Plan",     ghost: "PLAN",     bg: "bg-blue-50/50",    dot: "bg-blue-400",    text: "text-blue-600",    pos: "left-5 top-5"    },
  { id: "Q1" as Quadrant, label: "Q1 · Do First", ghost: "DO FIRST", bg: "bg-emerald-50/60", dot: "bg-emerald-400", text: "text-emerald-700", pos: "right-5 top-5"   },
  { id: "Q3" as Quadrant, label: "Q3 · Backlog",  ghost: "BACKLOG",  bg: "bg-slate-50/40",   dot: "bg-slate-300",   text: "text-slate-500",   pos: "left-5 bottom-5" },
  { id: "Q4" as Quadrant, label: "Q4 · Delegate", ghost: "DELEGATE", bg: "bg-amber-50/40",   dot: "bg-amber-400",   text: "text-amber-600",   pos: "right-5 bottom-5"},
] as const;

export function MatrixCanvas({ tasks, onMoveTask }: MatrixCanvasProps) {
  const boardRef = useRef<HTMLDivElement>(null);
  const [boardSize, setBoardSize] = useState({ width: FALLBACK_W, height: FALLBACK_H });
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const isMobile = useIsMobile();

  useEffect(() => {
    const el = boardRef.current;
    if (!el) return;
    const update = () => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) setBoardSize({ width: r.width, height: r.height });
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { width, height } = boardSize;
  const midX = width / 2;
  const midY = height / 2;

  const topTask = tasks
    .filter((t) => t.scheduledToday)
    .sort((a, b) => b.priorityScore - a.priorityScore)[0];

  const selectedTask = tasks.find((t) => t.id === selectedTaskId) ?? null;

  function handleSheetMove(quadrant: Quadrant) {
    if (selectedTaskId) {
      onMoveTask(selectedTaskId, quadrant);
      setSelectedTaskId(null);
    }
  }

  return (
    <div className="relative w-full">
      <div
        ref={boardRef}
        className="relative w-full overflow-hidden rounded-2xl border border-gray-200 bg-[#FAFAFA] shadow-sm"
        style={{ minHeight: isMobile ? 420 : 640 }}
      >
        {/* Quadrant tonal backgrounds + ghost watermark words */}
        <div className="absolute inset-0 grid grid-cols-2 grid-rows-2 pointer-events-none">
          {QUADRANTS.map(({ id, ghost, bg }) => (
            <div
              key={id}
              className={cn("relative flex items-center justify-center overflow-hidden", bg)}
            >
              <span className="absolute select-none font-black uppercase tracking-tight leading-none text-center text-gray-900 text-[72px] md:text-[96px] opacity-[0.04]">
                {ghost}
              </span>
            </div>
          ))}
        </div>

        {/* Dividers */}
        <div className="absolute top-0 bottom-0 left-1/2 w-px bg-gray-200 pointer-events-none" />
        <div className="absolute left-0 right-0 top-1/2 h-px bg-gray-200 pointer-events-none" />

        {/* Axis labels */}
        <div className="absolute left-3 top-1/2 -translate-y-1/2 -rotate-90 whitespace-nowrap text-[10px] font-semibold uppercase tracking-[0.3em] text-gray-300 pointer-events-none select-none">
          Importance
        </div>
        <div className="absolute bottom-3 right-5 text-[10px] font-semibold uppercase tracking-[0.3em] text-gray-300 pointer-events-none select-none">
          Urgency
        </div>

        {/* Corner labels with colored dot */}
        {QUADRANTS.map(({ id, label, dot, text, pos }) => (
          <div
            key={id}
            className={cn(
              "absolute z-20 flex items-center gap-1.5 rounded-full border border-gray-200 bg-white/90 px-2.5 py-1 shadow-sm pointer-events-none",
              pos
            )}
          >
            <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", dot)} />
            <span className={cn("text-[10px] font-bold uppercase tracking-[0.22em]", text)}>
              {label}
            </span>
          </div>
        ))}

        {/* Tiles */}
        <div className="absolute inset-0 z-10">
          {tasks.map((task) => {
            const { x, y } = taskToPoint(task, width, height);
            return (
              <DraggableBubble
                key={task.id}
                task={task}
                left={x}
                top={y}
                containerWidth={width}
                containerHeight={height}
                verticalDividerX={midX}
                horizontalDividerY={midY}
                isCritical={task.id === topTask?.id}
                isMobile={isMobile}
                onMoveTask={onMoveTask}
                onTap={setSelectedTaskId}
              />
            );
          })}
        </div>
      </div>

      {/* Mobile bottom sheet */}
      <BubbleSheet
        task={selectedTask}
        onMove={handleSheetMove}
        onDismiss={() => setSelectedTaskId(null)}
      />
    </div>
  );
}
```

**Step 2: Verify TypeScript — should be zero errors now**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

Expected: no errors

**Step 3: Commit**

```bash
cd frontend && git add src/components/matrix/MatrixCanvas.tsx
git commit -m "feat(matrix-v2): tonal quadrant backgrounds, ghost watermark text, dot corner labels"
```

---

### Task 4: Restyle BubbleSheet.tsx — tonal palette

**Files:**
- Modify: `frontend/src/components/matrix/BubbleSheet.tsx`

**Step 1: Replace the entire file**

```tsx
"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { BubbleSheetProps, Quadrant } from "@/components/matrix/types";

const QUADRANT_OPTIONS: {
  quadrant: Quadrant;
  label: string;
  sub: string;
  dot: string;
  bg: string;
  text: string;
  ring: string;
}[] = [
  { quadrant: "Q1", label: "Do First",  sub: "Urgent + Important",       dot: "bg-emerald-400", bg: "bg-emerald-50/70 border-emerald-200 hover:bg-emerald-100",  text: "text-emerald-700", ring: "ring-emerald-400" },
  { quadrant: "Q2", label: "Plan",      sub: "Important, not urgent",    dot: "bg-blue-400",    bg: "bg-blue-50/70 border-blue-200 hover:bg-blue-100",           text: "text-blue-700",    ring: "ring-blue-400"   },
  { quadrant: "Q3", label: "Backlog",   sub: "Neither urgent nor vital",  dot: "bg-slate-300",  bg: "bg-slate-50/70 border-slate-200 hover:bg-slate-100",        text: "text-slate-600",   ring: "ring-slate-300"  },
  { quadrant: "Q4", label: "Delegate",  sub: "Urgent, not important",    dot: "bg-amber-400",   bg: "bg-amber-50/70 border-amber-200 hover:bg-amber-100",        text: "text-amber-700",   ring: "ring-amber-400"  },
];

export function BubbleSheet({ task, onMove, onDismiss }: BubbleSheetProps) {
  return (
    <AnimatePresence>
      {task && (
        <>
          {/* Overlay */}
          <motion.div
            className="fixed inset-0 z-40 bg-black/40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onDismiss}
          />

          {/* Sheet */}
          <motion.div
            className="fixed bottom-0 left-0 right-0 z-50 rounded-t-3xl bg-[#FAFAFA] px-5 pb-10 pt-5 shadow-2xl"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 340, damping: 32 }}
            drag="y"
            dragConstraints={{ top: 0 }}
            dragElastic={0.2}
            onDragEnd={(_, info) => {
              if (info.offset.y > 80) onDismiss();
            }}
          >
            {/* Drag handle */}
            <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-gray-200" />

            <p className="mb-1 text-xs font-medium uppercase tracking-widest text-gray-400">
              Move task
            </p>
            <p className="mb-5 line-clamp-2 text-base font-semibold text-gray-900">
              {task.title}
            </p>

            <div className="grid grid-cols-2 gap-3">
              {QUADRANT_OPTIONS.map(({ quadrant, label, sub, dot, bg, text, ring }) => (
                <button
                  key={quadrant}
                  onClick={() => onMove(quadrant)}
                  className={`flex flex-col items-start gap-2 rounded-2xl border px-4 py-3 text-left transition-colors ${bg} ${
                    task.quadrant === quadrant ? `ring-2 ring-offset-1 ${ring}` : ""
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 shrink-0 rounded-full ${dot}`} />
                    <span className={`text-xs font-bold uppercase tracking-widest ${text}`}>
                      {quadrant}
                    </span>
                  </div>
                  <span className={`text-sm font-semibold ${text}`}>{label}</span>
                  <span className="text-xs text-gray-500">{sub}</span>
                </button>
              ))}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
```

**Step 2: Commit**

```bash
cd frontend && git add src/components/matrix/BubbleSheet.tsx
git commit -m "feat(matrix-v2): restyle BubbleSheet — tonal palette, dot indicators, FAFAFA bg"
```

---

### Task 5: Verify build

**Step 1: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

Expected: no errors

**Step 2: Production build**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: `✓ Compiled successfully`

**Step 3: Lint**

```bash
cd frontend && npm run lint 2>&1
```

Expected: no errors or warnings

**Step 4: Final commit if any tweaks were needed**

```bash
cd frontend && git add -p
git commit -m "fix(matrix-v2): post-build tweaks"
```
