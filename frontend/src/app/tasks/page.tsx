"use client";

import { useState, useEffect } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { TaskEditDrawer, TaskAddDrawer } from "@/components/tasks/TaskEditDrawer";
import { Task } from "@/types";
import { Check, Clock, Flame, Plus, Loader2, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { mapApiTask } from "@/lib/tasks";
import { useSchedule } from "@/lib/schedule-store";

const STATE_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-600",
  scheduled: "bg-blue-50 text-blue-700",
  in_progress: "bg-amber-50 text-amber-700",
  completed: "bg-emerald-50 text-emerald-700",
  missed: "bg-rose-50 text-rose-700",
  rescheduled: "bg-purple-50 text-purple-700",
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [editTask, setEditTask] = useState<Task | null>(null);
  const { rebuildAndRefresh } = useSchedule();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [addDrawerOpen, setAddDrawerOpen] = useState(false);
  const [filter, setFilter] = useState<"all" | "active" | "completed">("active");

  useEffect(() => {
    api.listTasks()
      .then((data: unknown[]) => setTasks(data.map((t, i) => mapApiTask(t as Record<string, unknown>, i))))
      .catch(() => setTasks([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = tasks.filter((t) => {
    if (filter === "active") return t.state !== "completed";
    if (filter === "completed") return t.state === "completed";
    return true;
  });

  function handleComplete(id: string) {
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, state: "completed" } : t)));
    api.completeTask(id)
      .then(() => rebuildAndRefresh())
      .catch(() => {});
  }
  async function handleSave(updated: Task) {
    setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    try {
      const saved = await api.updateTask(updated.id, {
        title: updated.title,
        deadline: updated.deadline,
        effort: updated.effort,
        notes: updated.notes,
      });
      setTasks((prev) =>
        prev.map((task, index) =>
          task.id === updated.id ? mapApiTask(saved as Record<string, unknown>, index) : task
        )
      );
    } catch {
      // Keep optimistic state for now.
    }
  }
  async function handleDelete(id: string) {
    setTasks((prev) => prev.filter((t) => t.id !== id));
    try {
      await api.deleteTask(id);
      rebuildAndRefresh().catch(() => {});
    } catch {
      // Keep optimistic removal for now.
    }
  }

  async function handleAddTask(data: { title: string; effort: Task["effort"]; deadline: string | null; notes: string | null }) {
    try {
      const created = await api.addTask({ title: data.title, effort: data.effort, deadline: data.deadline, notes: data.notes, importance: 3 });
      setTasks((prev) => [mapApiTask(created as Record<string, unknown>, 0), ...prev]);
      rebuildAndRefresh().catch(() => {});
    } catch {
      // silent — user can retry via add task button
    }
  }

  return (
    <AppLayout>
      <div className="flex-1 flex flex-col max-w-2xl w-full mx-auto px-4 md:px-8 py-8 pb-24 md:pb-8 gap-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight" style={{ color: "var(--foreground)" }}>Tasks</h1>
          <button
            onClick={() => setAddDrawerOpen(true)}
            className="flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-[var(--radius-md)] transition-colors"
            style={{ background: "var(--accent)", color: "#ffffff" }}
          >
            <Plus className="w-4 h-4" />
            Add task
          </button>
        </div>

        {/* Filter tabs */}
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
          {(["active", "all", "completed"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "text-sm font-medium px-3 py-1.5 rounded-md capitalize transition-colors",
                filter === f ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
              )}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Task list */}
        <div className="flex flex-col gap-2">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 text-gray-300 animate-spin" />
            </div>
          )}
          {!loading && filtered.length === 0 && (
            <div className="text-center py-12 text-gray-400 text-sm">No tasks here.</div>
          )}
          {filtered.map((task) => (
            <div key={task.id}>
            <div
              className={cn(
                "flex items-center gap-3 bg-white border rounded-xl px-4 py-3 group transition-colors hover:border-gray-300",
                task.is_primary ? "border-emerald-200" : "border-[var(--border)]"
              )}
            >
              <button
                onClick={() => handleComplete(task.id)}
                className={cn(
                  "w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors shrink-0",
                  task.state === "completed"
                    ? "bg-emerald-500 border-emerald-500"
                    : "border-gray-300 group-hover:border-emerald-400"
                )}
              >
                <Check
                  className={cn(
                    "w-3 h-3",
                    task.state === "completed" ? "text-white" : "text-transparent group-hover:text-emerald-400"
                  )}
                  strokeWidth={2.5}
                />
              </button>

              <button onClick={() => { setEditTask(task); setDrawerOpen(true); }} className="flex-1 text-left min-w-0">
                <p className={cn("text-sm font-medium", task.state === "completed" ? "line-through text-gray-400" : "text-gray-800")}>
                  {task.is_primary && (
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 mr-2 mb-0.5" />
                  )}
                  {task.title}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  {task.deadline && (
                    <span className="flex items-center gap-0.5 text-xs text-gray-400">
                      <Clock className="w-3 h-3" />
                      {new Date(task.deadline).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                    </span>
                  )}
                  <span className="flex items-center gap-0.5 text-xs text-gray-400">
                    <Flame className="w-3 h-3" />
                    {task.effort === "low" ? "1h" : task.effort === "high" ? "4h" : "2h"}
                  </span>
                </div>
              </button>

              <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full hidden sm:inline", STATE_COLORS[task.state])}>
                {task.state}
              </span>
            </div>

            {/* Steps */}
            {task.steps && task.steps.length > 0 && (
              <div className="ml-8 mt-1 flex flex-col gap-1 pb-2">
                {task.steps.map((step) => (
                  <div key={step.id} className="flex items-center gap-2">
                    <ChevronRight className="w-3 h-3 text-gray-300 shrink-0" />
                    <span className={cn(
                      "text-xs",
                      step.state === "completed" ? "line-through text-gray-300" : "text-gray-500"
                    )}>
                      {step.title}
                    </span>
                  </div>
                ))}
              </div>
            )}
            </div>
          ))}
        </div>
      </div>

      <TaskEditDrawer
        task={editTask}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onSave={handleSave}
        onDelete={handleDelete}
      />
      <TaskAddDrawer
        open={addDrawerOpen}
        onClose={() => setAddDrawerOpen(false)}
        onAdd={handleAddTask}
      />
    </AppLayout>
  );
}
