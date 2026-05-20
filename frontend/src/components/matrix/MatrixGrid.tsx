"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  DndContext,
  DragOverlay,
  closestCorners,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  useDroppable,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { TaskEditPanel } from "@/components/matrix/TaskEditPanel";
import type { MappedTask, Quadrant, MatrixCanvasProps } from "@/components/matrix/types";
import { quadrantCenter } from "@/lib/matrix";

// ─── Design tokens ────────────────────────────────────────────────────────────

const Q_CFG = {
  Q1: { label: "Do First",           sub: "Urgent · important",         color: "#dc2626", bg: "rgba(220,38,38,0.07)",   bgActive: "rgba(220,38,38,0.14)",  divider: "rgba(220,38,38,0.18)"  },
  Q2: { label: "Priority for Later", sub: "Important · not yet urgent", color: "#2563eb", bg: "rgba(37,99,235,0.07)",   bgActive: "rgba(37,99,235,0.14)",   divider: "rgba(37,99,235,0.18)"  },
  Q3: { label: "Low Priority",       sub: "If there's time",            color: "#64748b", bg: "rgba(100,116,139,0.06)", bgActive: "rgba(100,116,139,0.13)", divider: "rgba(100,116,139,0.18)" },
  Q4: { label: "Quick Tasks",        sub: "Urgent · low-stakes",        color: "#d97706", bg: "rgba(217,119,6,0.07)",   bgActive: "rgba(217,119,6,0.15)",   divider: "rgba(217,119,6,0.22)"  },
} as const;

const EFFORT_LABEL: Record<1 | 2 | 3, string> = { 1: "~1h", 2: "~2h", 3: "~4h" };

// Grid order: Q2 top-left, Q1 top-right, Q3 bottom-left, Q4 bottom-right
const GRID_ORDER: Quadrant[] = ["Q2", "Q1", "Q3", "Q4"];

type Order = Record<Quadrant, string[]>;

function buildOrder(tasks: MappedTask[]): Order {
  return {
    Q1: tasks.filter((t) => t.quadrant === "Q1").sort((a, b) => b.priorityScore - a.priorityScore).map((t) => t.id),
    Q2: tasks.filter((t) => t.quadrant === "Q2").sort((a, b) => b.priorityScore - a.priorityScore).map((t) => t.id),
    Q3: tasks.filter((t) => t.quadrant === "Q3").sort((a, b) => b.priorityScore - a.priorityScore).map((t) => t.id),
    Q4: tasks.filter((t) => t.quadrant === "Q4").sort((a, b) => b.priorityScore - a.priorityScore).map((t) => t.id),
  };
}

function findQuadrantForId(id: string, order: Order): Quadrant | null {
  for (const q of Object.keys(order) as Quadrant[]) {
    if (order[q].includes(id)) return q;
  }
  return null;
}

function parseZoneId(id: string): Quadrant | null {
  if (id.startsWith("zone-")) return id.replace("zone-", "") as Quadrant;
  return null;
}

// ─── SortableTaskRow ──────────────────────────────────────────────────────────

function SortableTaskRow({
  task,
  quadrant,
  isCritical,
  onTap,
}: {
  task: MappedTask;
  quadrant: Quadrant;
  isCritical: boolean;
  onTap: (taskId: string, el: HTMLElement) => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id });

  const cfg = Q_CFG[quadrant];

  return (
    <motion.div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        boxShadow: isDragging ? "0 8px 24px rgba(0,0,0,0.13)" : "0 1px 3px rgba(0,0,0,0.06)",
        cursor: isDragging ? "grabbing" : "grab",
      }}
      layout="position"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: isDragging ? 0.2 : 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.12 } }}
      transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
      className="group relative flex items-center gap-2.5 rounded-lg bg-white border border-transparent px-2.5 py-2.5 transition-shadow select-none"
      onClick={(e) => !isDragging && onTap(task.id, e.currentTarget as HTMLElement)}
    >
      {/* Decorative grip dots — visual hint only, not the drag target */}
      <div className="flex flex-col items-center gap-[3px] shrink-0 opacity-20 group-hover:opacity-50 transition-opacity">
        <span className="w-[3px] h-[3px] rounded-full" style={{ background: cfg.color }} />
        <span className="w-[3px] h-[3px] rounded-full" style={{ background: cfg.color }} />
        <span className="w-[3px] h-[3px] rounded-full" style={{ background: cfg.color }} />
        <span className="w-[3px] h-[3px] rounded-full" style={{ background: cfg.color }} />
        <span className="w-[3px] h-[3px] rounded-full" style={{ background: cfg.color }} />
        <span className="w-[3px] h-[3px] rounded-full" style={{ background: cfg.color }} />
      </div>

      <span className="h-[7px] w-[7px] shrink-0 rounded-full" style={{ background: cfg.color }} />

      <span className="flex-1 min-w-0 text-[13px] font-medium text-gray-900 leading-snug truncate">
        {task.title}
      </span>

      {isCritical && <span className="shrink-0 text-amber-400 text-[11px]">★</span>}

      {task.scheduledToday && (
        <span className="shrink-0 h-1.5 w-1.5 rounded-full bg-emerald-400" title="Scheduled today" />
      )}

      <span className="shrink-0 rounded-md border border-gray-100 bg-gray-50 px-[7px] py-0.5 font-mono text-[10px] font-semibold text-gray-400 tabular-nums">
        {EFFORT_LABEL[task.effort]}
      </span>
    </motion.div>
  );
}

// ─── QuadrantPanel ────────────────────────────────────────────────────────────

function QuadrantPanel({
  quadrant,
  tasks,
  isCritical,
  isActiveZone,
  onTap,
}: {
  quadrant: Quadrant;
  tasks: MappedTask[];
  isCritical: (id: string) => boolean;
  isActiveZone: boolean;
  onTap: (taskId: string, el: HTMLElement) => void;
}) {
  const cfg = Q_CFG[quadrant];
  const ids = tasks.map((t) => t.id);

  // useDroppable handles the case when dragging over an empty quadrant
  const { setNodeRef } = useDroppable({ id: `zone-${quadrant}` });

  return (
    <div
      className="flex flex-col min-h-0 transition-colors duration-150"
      style={{ background: isActiveZone ? cfg.bgActive : cfg.bg }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2.5 px-3.5 py-3 shrink-0"
        style={{ borderBottom: `1px solid ${cfg.divider}` }}
      >
        <div className="w-[3px] h-[18px] rounded-full shrink-0" style={{ background: cfg.color }} />
        <div className="flex-1 min-w-0">
          <p
            className="text-[11px] font-black uppercase tracking-[0.18em] leading-none"
            style={{ color: cfg.color }}
          >
            {cfg.label}
          </p>
          <p className="text-[9px] text-gray-400 mt-1 tracking-wide">{cfg.sub}</p>
        </div>
        <span
          className="shrink-0 text-[10px] font-bold tabular-nums px-2 py-0.5 rounded-full transition-all duration-150"
          style={{ background: `${cfg.color}18`, color: cfg.color }}
        >
          {tasks.length}
        </span>
      </div>

      {/* Task list — droppable zone */}
      <div ref={setNodeRef} className="flex-1 overflow-y-auto p-2.5 space-y-1.5 min-h-[120px]">
        <SortableContext items={ids} strategy={verticalListSortingStrategy}>
          <AnimatePresence initial={false}>
            {tasks.length === 0 ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center justify-center py-8 rounded-lg border-2 border-dashed select-none"
                style={{ borderColor: `${cfg.color}22` }}
              >
                <p className="text-[11px]" style={{ color: `${cfg.color}55` }}>
                  Drop tasks here
                </p>
              </motion.div>
            ) : (
              tasks.map((task) => (
                <SortableTaskRow
                  key={task.id}
                  task={task}
                  quadrant={quadrant}
                  isCritical={isCritical(task.id)}
                  onTap={onTap}
                />
              ))
            )}
          </AnimatePresence>
        </SortableContext>
      </div>
    </div>
  );
}

// ─── DragOverlay card ─────────────────────────────────────────────────────────

function OverlayCard({ task }: { task: MappedTask }) {
  const cfg = Q_CFG[task.quadrant];
  return (
    <div className="flex items-center gap-2 rounded-lg bg-white px-3 py-2.5 shadow-xl border border-gray-200 opacity-95 w-[240px]">
      <span className="h-[7px] w-[7px] shrink-0 rounded-full" style={{ background: cfg.color }} />
      <span className="flex-1 text-[13px] font-medium text-gray-900 truncate">{task.title}</span>
      <span className="shrink-0 rounded-md border border-gray-100 bg-gray-50 px-[7px] py-0.5 font-mono text-[10px] font-semibold text-gray-400">
        {EFFORT_LABEL[task.effort]}
      </span>
    </div>
  );
}

// ─── MatrixGrid ───────────────────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function MatrixGrid({ tasks, isEditing, onMoveTask, onUpdateTask, onTopTaskChange }: MatrixCanvasProps) {
  const [order, setOrder] = useState<Order>(() => buildOrder(tasks));
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeOverQ, setActiveOverQ] = useState<Quadrant | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<{
    taskId: string;
    anchor: { x: number; y: number };
  } | null>(null);

  // Sync order when external tasks list changes
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOrder((prev) => {
      const next: Order = { Q1: [], Q2: [], Q3: [], Q4: [] };
      const taskIds = new Set(tasks.map((t) => t.id));

      for (const q of Object.keys(prev) as Quadrant[]) {
        next[q] = prev[q].filter((id) => taskIds.has(id));
      }
      for (const t of tasks) {
        const placed = Object.values(next).some((ids) => ids.includes(t.id));
        if (!placed) next[t.quadrant].push(t.id);
      }
      return next;
    });
  }, [tasks]);

  const taskMap = useMemo(() => new Map(tasks.map((t) => [t.id, t])), [tasks]);
  // Top task = first item in the highest non-empty quadrant by Eisenhower priority (Q1→Q2→Q4→Q3).
  // Derived from the live list order so manual reordering is respected immediately.
  const topTaskId = useMemo(() => {
    for (const q of ["Q1", "Q2", "Q4", "Q3"] as Quadrant[]) {
      const firstId = order[q].find((id) => taskMap.has(id));
      if (firstId) return firstId;
    }
    return null;
  }, [order, taskMap]);

  const prevTopRef = useRef<string | null>(null);
  useEffect(() => {
    if (topTaskId !== prevTopRef.current) {
      prevTopRef.current = topTaskId;
      onTopTaskChange?.(topTaskId);
    }
  }, [topTaskId, onTopTaskChange]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } })
  );

  function handleDragStart({ active }: DragStartEvent) {
    setActiveId(active.id as string);
  }

  function handleDragOver({ active, over }: DragOverEvent) {
    if (!over) {
      setActiveOverQ(null);
      return;
    }

    const activeId = active.id as string;
    const overId = over.id as string;

    // Determine destination quadrant
    const destQ = parseZoneId(overId) ?? findQuadrantForId(overId, order);
    setActiveOverQ(destQ);

    if (!destQ) return;

    const sourceQ = findQuadrantForId(activeId, order);
    if (!sourceQ) return;

    if (sourceQ === destQ) {
      // Live within-quadrant reorder — shift items as you drag
      if (!parseZoneId(overId)) {
        setOrder((prev) => {
          const items = prev[sourceQ];
          const oldIdx = items.indexOf(activeId);
          const newIdx = items.indexOf(overId);
          if (oldIdx === -1 || newIdx === -1 || oldIdx === newIdx) return prev;
          return { ...prev, [sourceQ]: arrayMove(items, oldIdx, newIdx) };
        });
      }
    } else {
      // Live cross-quadrant preview — move item to destination
      setOrder((prev) => {
        if (!prev[sourceQ].includes(activeId)) return prev; // already moved
        const source = prev[sourceQ].filter((id) => id !== activeId);
        const dest = [...prev[destQ]];
        const overIdx = parseZoneId(overId) ? dest.length : dest.indexOf(overId);
        if (overIdx >= 0) { dest.splice(overIdx, 0, activeId); } else { dest.push(activeId); }
        return { ...prev, [sourceQ]: source, [destQ]: dest };
      });
    }
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    const activeId = active.id as string;
    setActiveId(null);
    setActiveOverQ(null);

    if (!over) {
      // Dropped outside — revert to original quadrant from tasks prop
      const original = tasks.find((t) => t.id === activeId);
      if (original) {
        setOrder((prev) => {
          // Remove from wherever it is now, put back in original quadrant
          const next = { ...prev };
          for (const q of Object.keys(next) as Quadrant[]) {
            next[q] = next[q].filter((id) => id !== activeId);
          }
          next[original.quadrant] = [...next[original.quadrant], activeId];
          return next;
        });
      }
      return;
    }

    // Figure out which quadrant it ended up in after live preview
    const destQ = findQuadrantForId(activeId, order);
    const originalQ = tasks.find((t) => t.id === activeId)?.quadrant;

    if (destQ && originalQ && destQ !== originalQ) {
      // Persist the cross-quadrant move
      const center = quadrantCenter(destQ);
      onMoveTask(activeId, { quadrant: destQ, urgency: center.urgency, importance: center.importance });
    }
  }

  function handleTap(taskId: string, el: HTMLElement) {
    if (activeId) return;
    const rect = el.getBoundingClientRect();
    setSelectedEntry({
      taskId,
      anchor: { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 },
    });
  }

  function handlePanelSave(taskId: string, updates: { title: string; effort: 1 | 2 | 3; quadrant: Quadrant }) {
    const task = tasks.find((t) => t.id === taskId);
    if (!task) return;

    if (updates.quadrant !== task.quadrant) {
      setOrder((prev) => {
        const srcQ = findQuadrantForId(taskId, prev) ?? task.quadrant;
        return {
          ...prev,
          [srcQ]: prev[srcQ].filter((id) => id !== taskId),
          [updates.quadrant]: [...prev[updates.quadrant], taskId],
        };
      });
    }

    onUpdateTask(taskId, updates);
    setSelectedEntry(null);
  }

  const selectedTask = selectedEntry ? (taskMap.get(selectedEntry.taskId) ?? null) : null;
  const activeTask = activeId ? (taskMap.get(activeId) ?? null) : null;

  return (
    <>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <div
          className="grid grid-cols-2 grid-rows-2 overflow-hidden rounded-2xl border border-gray-200 bg-[#FAFAFA] shadow-sm divide-x divide-y divide-gray-200/70"
          style={{ minHeight: 520 }}
        >
          {GRID_ORDER.map((q) => {
            const qTasks = (order[q] ?? [])
              .map((id) => taskMap.get(id))
              .filter((t): t is MappedTask => t !== undefined);
            return (
              <QuadrantPanel
                key={q}
                quadrant={q}
                tasks={qTasks}
                isCritical={(id) => id === topTaskId}
                isActiveZone={activeOverQ === q}
                onTap={handleTap}
              />
            );
          })}
        </div>

        <DragOverlay dropAnimation={{ duration: 160, easing: "cubic-bezier(0.22,1,0.36,1)" }}>
          {activeTask ? <OverlayCard task={activeTask} /> : null}
        </DragOverlay>
      </DndContext>

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
              tileW={0}
              onSave={handlePanelSave}
              onClose={() => setSelectedEntry(null)}
            />
          </>
        )}
      </AnimatePresence>
    </>
  );
}
