"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { AppLayout } from "@/components/layout/AppLayout";
import { MatrixGrid } from "@/components/matrix/MatrixGrid";
import type { MappedTask, Quadrant } from "@/components/matrix/types";
import { api } from "@/lib/api";
import { useSchedule } from "@/lib/schedule-store";
import {
  mapApiTaskToMatrixTask,
  matrixEffortToApiEffort,
  matrixPriorityScore,
  matrixTopTask,
  quadrantCenter,
  selectMatrixTasks,
} from "@/lib/matrix";

type MatrixFilter = "all" | "scheduled" | "unscheduled";

function mergeTask(tasks: MappedTask[], taskId: string, next: Partial<MappedTask>) {
  return tasks.map((task) => (task.id === taskId ? { ...task, ...next } : task));
}

export default function MatrixPage() {
  return (
    <AppLayout>
      <MatrixContent />
    </AppLayout>
  );
}

function MatrixContent() {
  const { rebuildAndRefresh } = useSchedule();
  const [tasks, setTasks] = useState<MappedTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<MatrixFilter>("all");

  useEffect(() => {
    api.listTasks()
      .then((data: Array<Record<string, unknown>>) => {
        setTasks(
          data
            .filter((task) => String(task.status ?? "pending") !== "completed")
            .map(mapApiTaskToMatrixTask)
        );
      })
      .catch(() => setTasks([]))
      .finally(() => setLoading(false));
  }, []);

  const selection = useMemo(
    () => selectMatrixTasks(tasks, query, filter, 999),
    [filter, query, tasks]
  );

  const scheduledCount = tasks.filter((task) => task.scheduledToday).length;
  const [topFocusId, setTopFocusId] = useState<string | null>(null);
  const topTask = useMemo(
    () => topFocusId ? tasks.find((t) => t.id === topFocusId) : matrixTopTask(tasks),
    [topFocusId, tasks]
  );

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


  function handleMoveTask(
    taskId: string,
    updates: { urgency: number; importance: number; quadrant: Quadrant }
  ) {
    const current = tasks.find((task) => task.id === taskId);
    if (!current) return;
    persistTask(
      taskId,
      {
        urgency_score: updates.urgency,
        importance_score: updates.importance,
      },
      {
        urgency: updates.urgency,
        importance: updates.importance,
        quadrant: updates.quadrant,
        priorityScore: matrixPriorityScore(updates.urgency, updates.importance, current.effort),
      }
    );
  }

  function handleUpdateTask(
    taskId: string,
    updates: { title: string; effort: 1 | 2 | 3; quadrant: Quadrant }
  ) {
    const center = quadrantCenter(updates.quadrant);
    persistTask(
      taskId,
      {
        title: updates.title,
        effort: matrixEffortToApiEffort(updates.effort),
        urgency_score: center.urgency,
        importance_score: center.importance,
      },
      {
        title: updates.title,
        effort: updates.effort,
        urgency: center.urgency,
        importance: center.importance,
        quadrant: updates.quadrant,
        priorityScore: matrixPriorityScore(center.urgency, center.importance, updates.effort),
      }
    );
  }

  return (
    <>
      <div className="flex-1 w-full px-4 md:px-8 py-8 pb-24 md:pb-8">
        <div className="mx-auto max-w-7xl flex flex-col gap-6">
          <div className="flex items-center justify-between gap-4">
            <h1 className="text-2xl font-semibold tracking-tight" style={{ color: "var(--foreground)" }}>
              Focus Matrix
            </h1>
            <div className="flex gap-3 shrink-0">
              <div
                className="rounded-xl px-4 py-2.5"
                style={{ border: "1px solid var(--border)", background: "var(--surface-elevated)" }}
              >
                <p className="text-[10px] font-medium uppercase tracking-[0.14em]" style={{ color: "var(--faint)" }}>Scheduled</p>
                <p className="text-xl font-semibold mt-0.5" style={{ color: "var(--foreground)" }}>{scheduledCount}</p>
              </div>
              <div
                className="rounded-xl px-4 py-2.5 min-w-[140px]"
                style={{ border: "1px solid var(--border)", background: "var(--surface-elevated)" }}
              >
                <p className="text-[10px] font-medium uppercase tracking-[0.14em]" style={{ color: "var(--faint)" }}>Top focus</p>
                <p className="text-sm font-medium mt-0.5 line-clamp-1" style={{ color: "var(--foreground)" }}>
                  {topTask?.title ?? "—"}
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-3 rounded-2xl border border-gray-200 bg-white p-4 md:flex-row md:items-center md:justify-between">
            <label className="flex items-center gap-2 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600 md:w-[320px]">
              <Search className="h-4 w-4 text-gray-400" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search tasks on the board..."
                className="w-full bg-transparent outline-none placeholder:text-gray-400"
              />
            </label>
            <div className="flex items-center gap-2">
              <div className="flex gap-2">
                {(["all", "scheduled", "unscheduled"] as MatrixFilter[]).map((value) => (
                  <button
                    key={value}
                    onClick={() => setFilter(value)}
                    className={`rounded-full px-3 py-1.5 text-xs font-medium capitalize ${
                      filter === value
                        ? "bg-emerald-500 text-white"
                        : "bg-gray-100 text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    {value}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {loading ? (
            <div className="rounded-2xl border border-gray-200 bg-white p-10 text-center text-sm text-gray-400">
              Loading the matrix...
            </div>
          ) : selection.visible.length === 0 ? (
            <div className="rounded-2xl border border-gray-200 bg-white p-10 text-center text-sm text-gray-400">
              No tasks match this filter yet.
            </div>
          ) : (
            <MatrixGrid
              tasks={selection.visible}
              isEditing={false}
              onMoveTask={handleMoveTask}
              onUpdateTask={handleUpdateTask}
              onTopTaskChange={setTopFocusId}
            />
          )}

        </div>
      </div>
    </>
  );
}
