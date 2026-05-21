"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Clock, Check } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Task } from "@/types";

interface SecondaryTasksProps {
  tasks: Task[];
  onComplete: (id: string) => void;
  onEdit: (task: Task) => void;
}

function formatDeadline(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const diff = Math.ceil((d.getTime() - Date.now()) / 86400000);
  if (diff === 0)  return "Today";
  if (diff === 1)  return "Tomorrow";
  if (diff < 0)   return `${Math.abs(diff)}d overdue`;
  return `${diff}d`;
}

export function SecondaryTasks({ tasks, onComplete, onEdit }: SecondaryTasksProps) {
  const [open, setOpen] = useState(false);

  if (tasks.length === 0) return null;

  return (
    <div className="w-full">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-sm font-medium py-2 transition-colors duration-150 cursor-pointer"
        style={{ color: open ? "var(--foreground)" : "var(--muted)" }}
        onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = "var(--foreground)"; }}
        onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = open ? "var(--foreground)" : "var(--muted)"; }}
      >
        {open ? (
          <ChevronUp className="w-3.5 h-3.5" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5" />
        )}
        {open ? "Hide" : `${tasks.length} more task${tasks.length > 1 ? "s" : ""} queued`}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <div className="flex flex-col gap-2 pt-1">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  className="flex items-center gap-3 rounded-[var(--radius-md)] px-4 py-3 group transition-all duration-150"
                  style={{
                    background: "var(--surface-elevated)",
                    border: "1px solid var(--border)",
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border-strong)";
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border)";
                  }}
                >
                  {/* Complete button */}
                  <button
                    onClick={() => onComplete(task.id)}
                    className="w-5 h-5 rounded-full flex items-center justify-center transition-all duration-150 shrink-0 cursor-pointer"
                    style={{ border: "1.5px solid var(--border-strong)" }}
                    onMouseEnter={e => {
                      (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--accent)";
                      (e.currentTarget as HTMLButtonElement).style.background = "var(--accent-surface)";
                    }}
                    onMouseLeave={e => {
                      (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border-strong)";
                      (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                    }}
                  >
                    <Check
                      className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity duration-150"
                      style={{ color: "var(--accent)" }}
                      strokeWidth={2.5}
                    />
                  </button>

                  {/* Task content */}
                  <button
                    onClick={() => onEdit(task)}
                    className="flex-1 text-left cursor-pointer"
                  >
                    <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                      {task.title}
                    </p>
                    {task.deadline && (
                      <p
                        className="flex items-center gap-1 mt-0.5 text-xs"
                        style={{ color: "var(--faint)", fontFamily: "var(--font-mono)" }}
                      >
                        <Clock className="w-3 h-3" />
                        {formatDeadline(task.deadline)}
                      </p>
                    )}
                  </button>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
