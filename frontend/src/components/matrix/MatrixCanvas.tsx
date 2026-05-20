"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { DraggableBubble } from "@/components/matrix/DraggableBubble";
import { TaskEditPanel } from "@/components/matrix/TaskEditPanel";
import type { MatrixCanvasProps, MappedTask, Quadrant } from "@/components/matrix/types";

const PADDING_DESKTOP = 64;
const PADDING_MOBILE = 36;
const FALLBACK_W = 1100;
const FALLBACK_H = 680;
const SNAP_GRID = 24;
const TILE_W_DESKTOP = 152;
const TILE_W_MOBILE = 116;

function clamp(v: number, lo: number, hi: number) {
  return Math.min(Math.max(v, lo), hi);
}

function taskToPoint(task: MappedTask, w: number, h: number, padding: number) {
  const usableW = Math.max(w - padding * 2, 200);
  const usableH = Math.max(h - padding * 2, 200);
  return {
    x: clamp(padding + (task.urgency / 100) * usableW, padding, w - padding),
    y: clamp(padding + (1 - task.importance / 100) * usableH, padding, h - padding),
  };
}

function pointToScores(cx: number, cy: number, w: number, h: number, padding: number) {
  const usableW = Math.max(w - padding * 2, 200);
  const usableH = Math.max(h - padding * 2, 200);
  const urgency = clamp(((cx - padding) / usableW) * 100, 0, 100);
  const importance = clamp((1 - (cy - padding) / usableH) * 100, 0, 100);
  return {
    urgency: Math.round(urgency),
    importance: Math.round(importance),
  };
}

function quadrantFromPosition(cx: number, cy: number, midX: number, midY: number): Quadrant {
  if (cx >= midX && cy < midY) return "Q1";
  if (cx < midX && cy < midY) return "Q2";
  if (cx < midX && cy >= midY) return "Q3";
  return "Q4";
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

const QUADRANTS = [
  { id: "Q2" as Quadrant, label: "Priority for Later", sub: "Important · not yet urgent", bgColor: "rgba(37,99,235,0.10)",   textColor: "#1d4ed8" },
  { id: "Q1" as Quadrant, label: "Do First",           sub: "Urgent · important",         bgColor: "rgba(220,38,38,0.13)",   textColor: "#dc2626" },
  { id: "Q3" as Quadrant, label: "Low Priority",       sub: "If there's time",            bgColor: "rgba(100,116,139,0.08)", textColor: "#475569" },
  { id: "Q4" as Quadrant, label: "Quick Tasks",        sub: "Urgent · low-stakes",        bgColor: "rgba(217,119,6,0.12)",   textColor: "#d97706" },
] as const;

export function MatrixCanvas({ tasks, isEditing, onMoveTask, onUpdateTask }: MatrixCanvasProps) {
  const boardRef = useRef<HTMLDivElement>(null);
  const [boardSize, setBoardSize] = useState({ width: FALLBACK_W, height: FALLBACK_H });
  const [selectedEntry, setSelectedEntry] = useState<{
    taskId: string;
    anchor: { x: number; y: number };
  } | null>(null);
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});
  const [dragKeys, setDragKeys] = useState<Record<string, number>>({});
  const positionsInitialized = useRef(false);
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
  const padding = isMobile ? PADDING_MOBILE : PADDING_DESKTOP;

  useEffect(() => {
    if (positionsInitialized.current) return;
    if (width === FALLBACK_W && height === FALLBACK_H) return;
    const init: Record<string, { x: number; y: number }> = {};
    for (const task of tasks) {
      init[task.id] = taskToPoint(task, width, height, padding);
    }
    setPositions(init);
    positionsInitialized.current = true;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [width, height]);

  useEffect(() => {
    if (!positionsInitialized.current) return;
    const missing = tasks.filter((t) => !positions[t.id]);
    if (missing.length === 0) return;
    setPositions((prev) => {
      const next = { ...prev };
      for (const t of missing) next[t.id] = taskToPoint(t, width, height, padding);
      return next;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks]);

  function handleDrop(taskId: string, cx: number, cy: number) {
    const snappedX = clamp(Math.round(cx / SNAP_GRID) * SNAP_GRID, 0, width);
    const snappedY = clamp(Math.round(cy / SNAP_GRID) * SNAP_GRID, 0, height);
    setPositions((prev) => ({ ...prev, [taskId]: { x: snappedX, y: snappedY } }));
    setDragKeys((prev) => ({ ...prev, [taskId]: (prev[taskId] ?? 0) + 1 }));
    const q = quadrantFromPosition(snappedX, snappedY, midX, midY);
    const scores = pointToScores(snappedX, snappedY, width, height, padding);
    onMoveTask(taskId, { quadrant: q, urgency: scores.urgency, importance: scores.importance });
  }

  function handlePanelSave(
    taskId: string,
    updates: { title: string; effort: 1 | 2 | 3; quadrant: Quadrant }
  ) {
    const task = tasks.find((t) => t.id === taskId);
    if (!task) return;

    // If quadrant changed, move tile to center of target quadrant
    if (updates.quadrant !== task.quadrant) {
      const qCenterX = updates.quadrant === "Q1" || updates.quadrant === "Q4" ? width * 0.75 : width * 0.25;
      const qCenterY = updates.quadrant === "Q1" || updates.quadrant === "Q2" ? height * 0.25 : height * 0.75;
      setPositions((prev) => ({ ...prev, [taskId]: { x: qCenterX, y: qCenterY } }));
      setDragKeys((prev) => ({ ...prev, [taskId]: (prev[taskId] ?? 0) + 1 }));
    }

    onUpdateTask(taskId, { title: updates.title, effort: updates.effort, quadrant: updates.quadrant });
    setSelectedEntry(null);
  }

  function handleTap(taskId: string) {
    const task = tasks.find((t) => t.id === taskId);
    if (!task) return;
    const pos = positions[taskId] ?? taskToPoint(task, width, height, padding);
    const rect = boardRef.current?.getBoundingClientRect();
    if (!rect) return;
    setSelectedEntry({
      taskId,
      anchor: { x: rect.left + pos.x, y: rect.top + pos.y },
    });
  }

  const topTask = tasks
    .filter((t) => t.scheduledToday)
    .sort((a, b) => b.priorityScore - a.priorityScore)[0];

  const selectedTask = selectedEntry
    ? (tasks.find((t) => t.id === selectedEntry.taskId) ?? null)
    : null;

  return (
    <div className="relative w-full">
      <div
        ref={boardRef}
        className="relative w-full overflow-hidden rounded-2xl border border-gray-200 bg-[#FAFAFA] shadow-sm"
        style={{ minHeight: isMobile ? 520 : 640 }}
      >
        {/* Dot grid */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: "radial-gradient(circle, #cbd5e1 1px, transparent 1px)",
            backgroundSize: `${SNAP_GRID * 2}px ${SNAP_GRID * 2}px`,
            opacity: 0.35,
          }}
        />

        {/* Quadrant backgrounds with centered bold labels */}
        <div className="absolute inset-0 grid grid-cols-2 grid-rows-2 pointer-events-none">
          {QUADRANTS.map(({ id, label, sub, bgColor, textColor }) => (
            <div
              key={id}
              className="relative flex flex-col items-center justify-center gap-1 overflow-hidden"
              style={{ background: bgColor }}
            >
              <span
                className="select-none text-center font-black uppercase leading-none tracking-tight px-6"
                style={{ color: textColor, opacity: 0.22, fontSize: "clamp(15px, 2.4vw, 28px)" }}
              >
                {label}
              </span>
              <span
                className="select-none text-center uppercase tracking-[0.14em]"
                style={{ color: textColor, opacity: 0.13, fontSize: "9px" }}
              >
                {sub}
              </span>
            </div>
          ))}
        </div>

        {/* Dividers */}
        <div className="absolute top-0 bottom-0 left-1/2 w-[1.5px] bg-gray-400/50 pointer-events-none" />
        <div className="absolute left-0 right-0 top-1/2 h-[1.5px] bg-gray-400/50 pointer-events-none" />

        {/* Axis labels with direction arrows */}
        <div className="absolute left-2 top-1/2 -translate-y-1/2 -rotate-90 whitespace-nowrap pointer-events-none select-none flex items-center gap-1">
          <span className="text-[9px] font-bold uppercase tracking-[0.25em] text-gray-400">↑ Importance</span>
        </div>
        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 pointer-events-none select-none flex items-center gap-1">
          <span className="text-[9px] font-bold uppercase tracking-[0.25em] text-gray-400">Urgency →</span>
        </div>


        {/* Tiles */}
        <div className="absolute inset-0 z-10">
          {tasks.map((task) => {
            const pos = positions[task.id] ?? taskToPoint(task, width, height, padding);
            return (
              <DraggableBubble
                key={`${task.id}-${dragKeys[task.id] ?? 0}`}
                task={task}
                left={pos.x}
                top={pos.y}
                containerWidth={width}
                containerHeight={height}
                isCritical={task.id === topTask?.id}
                isMobile={isMobile}
                isEditing={isEditing}
                onDrop={handleDrop}
                onTap={handleTap}
              />
            );
          })}
        </div>
      </div>

      {/* Modal + backdrop */}
      <AnimatePresence>
        {selectedTask && selectedEntry && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/20"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelectedEntry(null)}
            />
            <TaskEditPanel
              key={selectedTask.id}
              task={selectedTask}
              anchor={selectedEntry.anchor}
              tileW={isMobile ? TILE_W_MOBILE : TILE_W_DESKTOP}
              onSave={handlePanelSave}
              onClose={() => setSelectedEntry(null)}
            />
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
