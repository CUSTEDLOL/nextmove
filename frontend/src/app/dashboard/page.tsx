"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { ArrowUpRight, Clock3, ListTodo, Sparkles } from "lucide-react";
import { AppLayout } from "@/components/layout/AppLayout";
import { BrainDumpBar } from "@/components/dashboard/BrainDumpBar";
import { HeroTaskCard } from "@/components/dashboard/HeroTaskCard";
import { SecondaryTasks } from "@/components/dashboard/SecondaryTasks";
import { TaskEditDrawer } from "@/components/tasks/TaskEditDrawer";
import { OnboardingTour } from "@/components/onboarding/OnboardingTour";
import { Task } from "@/types";
import { api } from "@/lib/api";
import { mapApiTask } from "@/lib/tasks";
import { deriveDashboardTasks } from "./dashboard-state";
import { useSchedule } from "@/lib/schedule-store";

type ScheduleEntry = {
  id: string;
  task_title: string;
  start_time: string;
  end_time: string;
  entry_type: "block" | "deadline";
};

// Reusable stagger variant — subtle 6px lift, 300ms ease-out
function fadeUp(delay: number) {
  return {
    initial: { opacity: 0, y: 7 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.32, delay, ease: [0.22, 1, 0.36, 1] as const },
  };
}

function DashboardContent() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [schedule, setSchedule] = useState<ScheduleEntry[]>([]);
  const [editTask, setEditTask] = useState<Task | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showTour, setShowTour] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("nextmove_tour_done") !== "true";
  });
  const { rebuildAndRefresh } = useSchedule();

  async function fetchDashboardData() {
    return await Promise.all([
      api.getTodayTasks(),
      api.getScheduleBlocks(),
    ]) as [{ primary?: unknown; secondary?: unknown[] }, ScheduleEntry[]];
  }

  function applyDashboardData(
    todayData: { primary?: unknown; secondary?: unknown[] },
    scheduleData: ScheduleEntry[]
  ) {
    const all: Task[] = [];
    if (todayData.primary) all.push(mapApiTask(todayData.primary as Record<string, unknown>, 0));
    (todayData.secondary ?? []).forEach((t, i) =>
      all.push(mapApiTask(t as Record<string, unknown>, i + 1))
    );
    setTasks(all);
    setSchedule(scheduleData.filter((entry) => entry.entry_type === "block").slice(0, 3));
  }

  async function refreshDashboard() {
    const [todayData, scheduleData] = await fetchDashboardData();
    applyDashboardData(todayData, scheduleData);
  }

  useEffect(() => {
    let cancelled = false;
    fetchDashboardData()
      .then(([todayData, scheduleData]) => {
        if (cancelled) return;
        applyDashboardData(todayData, scheduleData);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const { primaryTask, secondaryTasks, isQueueEmpty } = deriveDashboardTasks(tasks);

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long", month: "long", day: "numeric",
  });

  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good morning" :
    hour < 17 ? "Good afternoon" :
    "Good evening";

  async function handleComplete(id: string) {
    setTasks((prev) =>
      prev.map((t) => (t.id === id ? { ...t, state: "completed" } : t))
    );
    try {
      await api.completeTask(id);
      await Promise.all([refreshDashboard(), rebuildAndRefresh()]);
    } catch {
      // Keep the optimistic completion state.
    }
  }

  function handleEdit(task: Task) {
    setEditTask(task);
    setDrawerOpen(true);
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
      const nextSchedule = await api.getScheduleBlocks();
      setSchedule(
        (nextSchedule as ScheduleEntry[]).filter((e) => e.entry_type === "block").slice(0, 3)
      );
    } catch {
      // Keep optimistic state.
    }
  }

  async function handleDelete(id: string) {
    setTasks((prev) => prev.filter((t) => t.id !== id));
    try {
      await api.deleteTask(id);
      const nextSchedule = await api.getScheduleBlocks();
      setSchedule(
        (nextSchedule as ScheduleEntry[]).filter((e) => e.entry_type === "block").slice(0, 3)
      );
    } catch {
      // Keep optimistic removal.
    }
  }

  async function handleDump(text: string) {
    const data = await api.brainDump(text) as { tasks?: Array<Record<string, unknown>> };
    rebuildAndRefresh().catch(() => {});
    try {
      await refreshDashboard();
    } catch {
      // Keep the optimistic confirmation.
    }
    const titles = (data.tasks ?? []).map((task) => String(task.title ?? "Untitled task"));
    return { createdCount: titles.length, titles };
  }

  return (
    <>
      <div className="flex-1 flex flex-col max-w-2xl w-full mx-auto px-4 md:px-8 py-8 pb-24 md:pb-8 gap-6">

        {/* Date header */}
        <motion.div {...fadeUp(0)}>
          <p
            className="text-[11px] font-medium uppercase tracking-[0.14em] mb-1"
            style={{ color: "var(--faint)", fontFamily: "var(--font-mono)" }}
          >
            {today}
          </p>
          <h1 className="text-2xl font-semibold tracking-tight" style={{ color: "var(--foreground)" }}>
            {greeting}
          </h1>
        </motion.div>

        {/* Brain dump */}
        <motion.div {...fadeUp(0.07)}>
          <BrainDumpBar onSubmit={handleDump} />
        </motion.div>

        {/* Hero task */}
        <motion.div {...fadeUp(0.14)}>
          {primaryTask ? (
            <HeroTaskCard
              task={primaryTask}
              onComplete={handleComplete}
              onEdit={handleEdit}
            />
          ) : (
            <section
              className="relative overflow-hidden rounded-[1.5rem] p-6"
              style={{
                border: "1px solid var(--border)",
                background: "linear-gradient(140deg, #fffdf3 0%, #f5fbf5 45%, #eef8ff 100%)",
                boxShadow: "var(--shadow-raised)",
              }}
            >
              <div className="absolute inset-y-0 right-0 w-40 pointer-events-none"
                style={{ background: "radial-gradient(circle at center, rgba(27,107,72,0.12), transparent 70%)" }}
              />
              <div className="relative">
                <div
                  className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-[0.18em]"
                  style={{ fontFamily: "var(--font-mono)", color: "var(--accent)" }}
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  Runway Clear
                </div>
                <div className="mt-4 flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
                  <div className="max-w-xl">
                    <h2
                      className="font-display leading-[1.2]"
                      style={{ fontSize: "1.6rem", color: "var(--foreground)" }}
                    >
                      No active focus item right now.
                    </h2>
                    <p className="mt-3 text-sm leading-6" style={{ color: "var(--muted)" }}>
                      You cleared the current queue. Use the dump bar above to tee up the next
                      commitment while the day is still warm.
                    </p>
                  </div>
                  <div
                    className="rounded-xl px-4 py-3 backdrop-blur shrink-0"
                    style={{ border: "1px solid rgba(255,255,255,0.8)", background: "rgba(255,255,255,0.75)" }}
                  >
                    <div className="flex items-center gap-2 text-xs font-medium" style={{ color: "var(--foreground)" }}>
                      <Clock3 className="h-4 w-4" style={{ color: "var(--accent)" }} />
                      Short task, big momentum
                    </div>
                    <p className="mt-1 text-xs leading-5" style={{ color: "var(--muted)" }}>
                      Even 15 minutes is enough to reopen the flow.
                    </p>
                  </div>
                </div>
                <div className="mt-6 grid gap-3 md:grid-cols-2">
                  <div
                    className="rounded-xl p-4"
                    style={{ border: "1px solid rgba(255,255,255,0.7)", background: "rgba(255,255,255,0.8)" }}
                  >
                    <div className="flex items-center gap-2 text-xs font-medium" style={{ color: "var(--foreground)" }}>
                      <ListTodo className="h-4 w-4" style={{ color: "var(--accent)" }} />
                      Next move
                    </div>
                    <p className="mt-2 text-sm font-medium" style={{ color: "var(--foreground)" }}>
                      Dump the next task with a deadline or time.
                    </p>
                    <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
                      Classes, errands, assignments, calls, prep work. Just throw it in above.
                    </p>
                  </div>
                  <div
                    className="rounded-xl p-4"
                    style={{ background: "var(--foreground)", border: "1px solid transparent" }}
                  >
                    <div
                      className="flex items-center gap-2 text-xs font-medium"
                      style={{ color: "var(--accent-bright)" }}
                    >
                      <ArrowUpRight className="h-4 w-4" />
                      Momentum tip
                    </div>
                    <p className="mt-2 text-sm font-medium text-white">
                      Keep the queue alive before context cools off.
                    </p>
                    <p className="mt-1 text-sm" style={{ color: "#A8A29E" }}>
                      The best next task is usually the one you already know is coming.
                    </p>
                  </div>
                </div>
              </div>
            </section>
          )}
        </motion.div>

        {/* Secondary tasks */}
        {!isQueueEmpty && (
          <motion.div {...fadeUp(0.21)}>
            <SecondaryTasks
              tasks={secondaryTasks}
              onComplete={handleComplete}
              onEdit={handleEdit}
            />
          </motion.div>
        )}

        {/* Upcoming blocks */}
        <motion.div {...fadeUp(0.28)}>
          <section
            className="rounded-2xl p-5"
            style={{ border: "1px solid var(--border)", background: "var(--surface-elevated)" }}
          >
            <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--foreground)" }}>
              Upcoming blocks
            </h2>
            <div className="flex flex-col gap-2">
              {schedule.length === 0 ? (
                <p className="text-sm" style={{ color: "var(--faint)" }}>
                  No blocks scheduled yet.
                </p>
              ) : (
                schedule.map((entry) => (
                  <div
                    key={entry.id}
                    className="flex items-center justify-between rounded-[var(--radius-md)] px-4 py-3"
                    style={{ background: "var(--surface)" }}
                  >
                    <div>
                      <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                        {entry.task_title}
                      </p>
                      <p
                        className="text-xs mt-0.5"
                        style={{ fontFamily: "var(--font-mono)", color: "var(--faint)" }}
                      >
                        {new Date(entry.start_time).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
                        {" – "}
                        {new Date(entry.end_time).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>
        </motion.div>
      </div>

      <TaskEditDrawer
        task={editTask}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onSave={handleSave}
        onDelete={handleDelete}
      />
      {showTour && (
        <OnboardingTour
          onComplete={() => {
            localStorage.setItem("nextmove_tour_done", "true");
            setShowTour(false);
          }}
        />
      )}
    </>
  );
}

export default function DashboardPage() {
  return (
    <AppLayout>
      <DashboardContent />
    </AppLayout>
  );
}
