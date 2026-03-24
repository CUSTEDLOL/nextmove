# Focus Matrix Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Completely rewrite the `/matrix` page and its components to produce a clean, polished Focus Matrix that looks great on desktop and mobile.

**Architecture:** Full rewrite of three existing files (`page.tsx`, `MatrixCanvas.tsx`, `DraggableBubble.tsx`) plus one new file (`BubbleSheet.tsx`). Desktop uses framer-motion drag-and-drop. Mobile uses tap-to-assign via a bottom sheet. All data is hardcoded mock.

**Tech Stack:** Next.js 14 (App Router), TypeScript, Tailwind CSS, framer-motion, lucide-react

---

### Task 1: Update types.ts

**Files:**
- Modify: `frontend/src/components/matrix/types.ts`

**Step 1: Replace the entire file with the updated types**

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
  left: number;
  top: number;
  size: number;
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

**Step 2: Verify TypeScript sees the file (errors in other files are expected at this point)**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "matrix/types" | head -5
```

Expected: no errors in `types.ts` itself

**Step 3: Commit**

```bash
git add frontend/src/components/matrix/types.ts
git commit -m "feat(matrix): update types — add Quadrant, onMoveTask, BubbleSheetProps"
```

---

### Task 2: Rewrite page.tsx

**Files:**
- Modify: `frontend/src/app/matrix/page.tsx`

**Step 1: Replace the entire file**

```tsx
"use client";

import { useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { MatrixCanvas } from "@/components/matrix/MatrixCanvas";
import type { MappedTask, Quadrant } from "@/components/matrix/types";
import { Sparkles } from "lucide-react";

function deriveScheduled(quadrant: Quadrant): boolean {
  return quadrant === "Q1";
}

const INITIAL_TASKS: MappedTask[] = [
  { id: "t1", title: "Finish chemistry lab report", urgency: 92, importance: 88, priorityScore: 96, effort: 3, scheduledToday: true,  quadrant: "Q1" },
  { id: "t2", title: "Revise presentation outline",  urgency: 78, importance: 84, priorityScore: 87, effort: 2, scheduledToday: true,  quadrant: "Q1" },
  { id: "t3", title: "Reply to project teammate",    urgency: 64, importance: 71, priorityScore: 69, effort: 1, scheduledToday: true,  quadrant: "Q1" },
  { id: "t4", title: "Organize lecture notes",       urgency: 36, importance: 68, priorityScore: 49, effort: 2, scheduledToday: false, quadrant: "Q2" },
  { id: "t5", title: "Book study room for Friday",   urgency: 72, importance: 34, priorityScore: 34, effort: 1, scheduledToday: false, quadrant: "Q4" },
  { id: "t6", title: "Review saved research links",  urgency: 18, importance: 28, priorityScore: 27, effort: 1, scheduledToday: false, quadrant: "Q3" },
];

export default function MatrixPage() {
  const [tasks, setTasks] = useState<MappedTask[]>(INITIAL_TASKS);

  function handleMoveTask(taskId: string, quadrant: Quadrant) {
    setTasks((prev) =>
      prev.map((t) =>
        t.id === taskId
          ? { ...t, quadrant, scheduledToday: deriveScheduled(quadrant) }
          : t
      )
    );
  }

  const scheduledCount = tasks.filter((t) => t.scheduledToday).length;
  const topTask = tasks
    .filter((t) => t.scheduledToday)
    .sort((a, b) => b.priorityScore - a.priorityScore)[0];

  return (
    <AppLayout>
      <div className="flex-1 w-full px-4 md:px-8 py-8 pb-24 md:pb-8">
        <div className="mx-auto max-w-7xl flex flex-col gap-6">

          {/* Header */}
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div className="space-y-2 max-w-xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                <Sparkles className="h-3.5 w-3.5" />
                Focus Matrix
              </div>
              <h1 className="text-3xl md:text-4xl font-semibold tracking-tight text-gray-900">
                Map your work into the quadrants that matter.
              </h1>
              <p className="text-sm md:text-base text-gray-500">
                Urgency increases right. Importance increases up. Drag tasks — or tap to reassign.
              </p>
            </div>

            <div className="flex gap-3 md:min-w-[280px]">
              <div className="flex-1 rounded-2xl border border-gray-200 bg-white px-4 py-3 shadow-sm">
                <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Scheduled today</p>
                <p className="mt-1 text-2xl font-semibold text-gray-900">{scheduledCount}</p>
              </div>
              <div className="flex-1 rounded-2xl border border-gray-200 bg-white px-4 py-3 shadow-sm">
                <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Top focus</p>
                <p className="mt-1 text-sm font-medium leading-5 text-gray-900 line-clamp-2">
                  {topTask?.title ?? "—"}
                </p>
              </div>
            </div>
          </div>

          <MatrixCanvas tasks={tasks} onMoveTask={handleMoveTask} />
        </div>
      </div>
    </AppLayout>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/app/matrix/page.tsx
git commit -m "feat(matrix): rewrite page.tsx — clean header, stats, quadrant-aware mock data"
```

---

### Task 3: Create BubbleSheet.tsx

**Files:**
- Create: `frontend/src/components/matrix/BubbleSheet.tsx`

**Step 1: Create the file**

```tsx
"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { BubbleSheetProps, Quadrant } from "@/components/matrix/types";

const QUADRANT_OPTIONS: {
  quadrant: Quadrant;
  label: string;
  sub: string;
  color: string;
  bg: string;
}[] = [
  { quadrant: "Q1", label: "Do First",  sub: "Urgent + Important",      color: "text-emerald-700", bg: "bg-emerald-50 border-emerald-200 hover:bg-emerald-100" },
  { quadrant: "Q2", label: "Plan",      sub: "Important, not urgent",   color: "text-blue-700",    bg: "bg-blue-50 border-blue-200 hover:bg-blue-100" },
  { quadrant: "Q3", label: "Backlog",   sub: "Neither urgent nor vital", color: "text-gray-600",   bg: "bg-gray-50 border-gray-200 hover:bg-gray-100" },
  { quadrant: "Q4", label: "Delegate",  sub: "Urgent, not important",   color: "text-orange-700",  bg: "bg-orange-50 border-orange-200 hover:bg-orange-100" },
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
            className="fixed bottom-0 left-0 right-0 z-50 rounded-t-3xl bg-white px-5 pb-10 pt-5 shadow-2xl"
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

            <p className="mb-1 text-xs font-medium uppercase tracking-widest text-gray-400">Move task</p>
            <p className="mb-5 text-base font-semibold text-gray-900 line-clamp-2">{task.title}</p>

            <div className="grid grid-cols-2 gap-3">
              {QUADRANT_OPTIONS.map(({ quadrant, label, sub, color, bg }) => (
                <button
                  key={quadrant}
                  onClick={() => onMove(quadrant)}
                  className={`flex flex-col items-start gap-1 rounded-2xl border px-4 py-3 text-left transition-colors ${bg} ${
                    task.quadrant === quadrant ? "ring-2 ring-offset-1 ring-current" : ""
                  }`}
                >
                  <span className={`text-xs font-bold uppercase tracking-widest ${color}`}>{quadrant}</span>
                  <span className={`text-sm font-semibold ${color}`}>{label}</span>
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
git add frontend/src/components/matrix/BubbleSheet.tsx
git commit -m "feat(matrix): add BubbleSheet — mobile tap-to-assign bottom sheet"
```

---

### Task 4: Rewrite DraggableBubble.tsx

**Files:**
- Modify: `frontend/src/components/matrix/DraggableBubble.tsx`

**Step 1: Replace the entire file**

```tsx
"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DraggableBubbleProps, Quadrant } from "@/components/matrix/types";

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

export function DraggableBubble({
  task,
  left,
  top,
  size,
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
  const diameter = clamp(Math.round(size), 72, 144);
  const maxLeft = Math.max(containerWidth - diameter, 0);
  const maxTop = Math.max(containerHeight - diameter, 0);
  const x = clamp(left, 0, maxLeft);
  const y = clamp(top, 0, maxTop);
  const shouldGlow = isCritical && task.scheduledToday;
  const bubbleCenterX = x + diameter / 2;
  const bubbleCenterY = y + diameter / 2;

  return (
    <motion.div
      className="absolute touch-none select-none"
      style={{
        left: x,
        top: y,
        width: diameter,
        height: diameter,
        zIndex: isDragging ? 50 : shouldGlow ? 30 : 10,
      }}
      drag={!isMobile}
      dragElastic={0.12}
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
        const finalCX = bubbleCenterX + info.offset.x;
        const finalCY = bubbleCenterY + info.offset.y;
        const q = quadrantFromPosition(finalCX, finalCY, verticalDividerX, horizontalDividerY);
        onMoveTask(task.id, q);
      }}
      onTap={() => {
        if (isMobile) onTap(task.id);
      }}
      whileTap={{ scale: isMobile ? 0.93 : 0.98 }}
      aria-label={`${task.title}, priority ${task.priorityScore}, ${task.quadrant}`}
    >
      <motion.div
        className={cn(
          "relative flex h-full w-full items-center justify-center overflow-hidden rounded-full border",
          task.scheduledToday
            ? "border-emerald-300 bg-white shadow-[0_8px_32px_rgba(16,185,129,0.22)]"
            : "border-gray-200 bg-white shadow-[0_6px_24px_rgba(15,23,42,0.10)]",
          shouldGlow && "border-emerald-400 shadow-[0_8px_40px_rgba(16,185,129,0.35)]"
        )}
        animate={
          isDragging
            ? { scale: 1.05 }
            : { y: [0, -4, 0], scale: shouldGlow ? [1, 1.02, 1] : 1 }
        }
        transition={
          isDragging
            ? { type: "spring", stiffness: 400, damping: 28 }
            : {
                y: { duration: 7, repeat: Infinity, ease: "easeInOut" },
                scale: { duration: 3, repeat: Infinity, ease: "easeInOut" },
              }
        }
        whileHover={!isMobile ? { scale: 1.06 } : {}}
      >
        {/* Pulse glow for top priority */}
        {shouldGlow && (
          <div className="absolute inset-[-20%] rounded-full bg-emerald-400/15 blur-2xl animate-pulse" />
        )}

        {/* Scheduled ring */}
        {task.scheduledToday && (
          <div className="absolute inset-0 rounded-full ring-2 ring-emerald-300/60" />
        )}

        <div className="relative z-10 flex flex-col items-center justify-center gap-0.5 px-3 text-center">
          <p
            className={cn(
              "line-clamp-2 w-full font-semibold tracking-tight text-gray-900",
              diameter >= 120 ? "text-sm" : diameter >= 96 ? "text-[13px]" : "text-[11px]"
            )}
            title={task.title}
          >
            {task.title}
          </p>

          <div className="flex items-center justify-center gap-0.5 mt-0.5">
            {Array.from({ length: task.effort }).map((_, i) => (
              <Zap
                key={i}
                className={cn(
                  "h-2.5 w-2.5 shrink-0",
                  task.scheduledToday ? "text-emerald-500" : "text-amber-400"
                )}
                fill="currentColor"
                strokeWidth={0}
              />
            ))}
          </div>

          {task.scheduledToday && diameter >= 88 && (
            <span className="mt-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-emerald-700">
              Today
            </span>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/matrix/DraggableBubble.tsx
git commit -m "feat(matrix): rewrite DraggableBubble — cleaner visuals, mobile tap, quadrant-aware drag"
```

---

### Task 5: Rewrite MatrixCanvas.tsx

**Files:**
- Modify: `frontend/src/components/matrix/MatrixCanvas.tsx`

**Step 1: Replace the entire file**

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
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

function bubbleSize(task: MappedTask) {
  return 80 + (task.priorityScore / 100) * 60;
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
        className="relative w-full overflow-hidden rounded-3xl border border-gray-200 bg-white shadow-sm"
        style={{ minHeight: isMobile ? 420 : 640 }}
      >
        {/* Quadrant backgrounds — 2x2 CSS grid */}
        <div className="absolute inset-0 grid grid-cols-2 grid-rows-2 pointer-events-none">
          <div className="bg-slate-50/70" />       {/* Q2: top-left  — Plan      */}
          <div className="bg-emerald-50/80" />     {/* Q1: top-right — Do First  */}
          <div className="bg-white" />              {/* Q3: bot-left  — Backlog   */}
          <div className="bg-white" />              {/* Q4: bot-right — Delegate  */}
        </div>

        {/* Dividers */}
        <div className="absolute top-0 bottom-0 left-1/2 w-px bg-gray-200 pointer-events-none" />
        <div className="absolute left-0 right-0 top-1/2 h-px bg-gray-200 pointer-events-none" />

        {/* Axis labels */}
        <div className="absolute left-3 top-1/2 -translate-y-1/2 -rotate-90 text-[10px] font-semibold uppercase tracking-[0.3em] text-gray-300 pointer-events-none select-none whitespace-nowrap">
          Importance
        </div>
        <div className="absolute bottom-3 right-5 text-[10px] font-semibold uppercase tracking-[0.3em] text-gray-300 pointer-events-none select-none">
          Urgency
        </div>

        {/* Quadrant corner labels */}
        <div className="absolute left-5 top-5 z-20 rounded-full border border-slate-200 bg-white/90 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.22em] text-slate-500 shadow-sm pointer-events-none">
          Q2 · Plan
        </div>
        <div className="absolute right-5 top-5 z-20 rounded-full border border-emerald-200 bg-white/90 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.22em] text-emerald-700 shadow-sm pointer-events-none">
          Q1 · Do First
        </div>
        <div className="absolute left-5 bottom-5 z-20 rounded-full border border-slate-200 bg-white/90 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.22em] text-slate-500 shadow-sm pointer-events-none">
          Q3 · Backlog
        </div>
        <div className="absolute right-5 bottom-5 z-20 rounded-full border border-slate-200 bg-white/90 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.22em] text-slate-500 shadow-sm pointer-events-none">
          Q4 · Delegate
        </div>

        {/* Bubbles */}
        <div className="absolute inset-0 z-10">
          {tasks.map((task) => {
            const { x, y } = taskToPoint(task, width, height);
            const size = bubbleSize(task);
            return (
              <DraggableBubble
                key={task.id}
                task={task}
                left={x - size / 2}
                top={y - size / 2}
                size={size}
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

**Step 2: Commit**

```bash
git add frontend/src/components/matrix/MatrixCanvas.tsx
git commit -m "feat(matrix): rewrite MatrixCanvas — clean quadrants, solid dividers, mobile sheet wiring"
```

---

### Task 6: Verify build and visual

**Step 1: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

Expected: no errors

**Step 2: Run Next.js build**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully`

**Step 3: Start dev server and verify**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000/matrix` and confirm:
- 4 quadrants visible: Q1 has a soft emerald tint, others are white/slate
- Solid gray divider lines crossing at center
- Axis labels (Importance, Urgency) and quadrant corner labels visible
- Bubbles positioned correctly: high-urgency tasks on the right, high-importance at top
- Top-priority bubble has a subtle emerald glow and ring
- Desktop: drag a bubble to a new quadrant → it updates (scheduled/unscheduled)
- Mobile (resize browser to <768px): tap a bubble → bottom sheet slides up → tap a quadrant → bubble moves, sheet closes

**Step 4: Final commit if any visual tweaks were made**

```bash
git add -p
git commit -m "feat(matrix): complete Focus Matrix redesign — desktop drag, mobile bottom sheet"
```
