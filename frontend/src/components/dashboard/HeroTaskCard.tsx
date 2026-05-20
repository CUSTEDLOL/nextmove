"use client";

import { Check, Clock, ChevronRight } from "lucide-react";
import { Task } from "@/types";

interface HeroTaskCardProps {
  task: Task;
  onComplete: (id: string) => void;
  onEdit: (task: Task) => void;
}

function effortLabel(effort: Task["effort"]): string {
  if (effort === "low")  return "~1h";
  if (effort === "high") return "~4h";
  return "~2h";
}

function formatDeadline(iso: string | null): string {
  if (!iso) return "No deadline";
  const d = new Date(iso);
  const today = new Date();
  const diff = Math.ceil((d.getTime() - today.getTime()) / 86400000);
  if (diff === 0)  return "Due today";
  if (diff === 1)  return "Due tomorrow";
  if (diff < 0)   return `${Math.abs(diff)}d overdue`;
  return `Due in ${diff}d`;
}

function deadlineColor(iso: string | null): string {
  if (!iso) return "var(--faint)";
  const diff = Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000);
  if (diff < 0)  return "#C0392B";
  if (diff === 0) return "#B45309";
  return "var(--muted)";
}

export function HeroTaskCard({ task, onComplete, onEdit }: HeroTaskCardProps) {
  return (
    <div
      className="w-full rounded-2xl overflow-hidden"
      style={{
        background: "var(--surface-elevated)",
        border: "1px solid var(--border)",
        boxShadow: "var(--shadow-raised)",
      }}
    >
      {/* Accent bar — 3px, anchors the card visually */}
      <div className="h-[3px]" style={{ background: "var(--accent)" }} />

      <div className="p-6">
        {/* Label */}
        <div className="mb-3">
          <span
            className="text-[10px] font-medium uppercase tracking-[0.18em]"
            style={{ fontFamily: "var(--font-mono)", color: "var(--accent)" }}
          >
            Today&apos;s Focus
          </span>
        </div>

        {/* Title — display font, the ONE important thing */}
        <h2
          className="font-display leading-[1.2] tracking-[-0.01em] text-[1.65rem]"
          style={{ color: "var(--foreground)" }}
        >
          {task.title}
        </h2>

        {/* Meta */}
        <div className="flex items-center gap-3 mt-4">
          <span
            className="inline-flex items-center text-[11px] px-2 py-0.5 rounded-[var(--radius-sm)]"
            style={{
              fontFamily: "var(--font-mono)",
              background: "var(--surface)",
              border: "1px solid var(--border)",
              color: "var(--muted)",
            }}
          >
            {effortLabel(task.effort)}
          </span>
          <span
            className="flex items-center gap-1 text-xs"
            style={{ color: deadlineColor(task.deadline), fontFamily: "var(--font-sans)" }}
          >
            <Clock className="w-3.5 h-3.5" />
            {formatDeadline(task.deadline)}
          </span>
        </div>

        {/* Notes — left border treatment, reads as annotation */}
        {task.notes && (
          <p
            className="text-sm leading-relaxed mt-4 pl-3"
            style={{
              borderLeft: "2px solid var(--border)",
              color: "var(--muted)",
            }}
          >
            {task.notes}
          </p>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3 mt-6">
          <button
            onClick={() => onComplete(task.id)}
            className="flex-1 flex items-center justify-center gap-2 text-sm font-medium rounded-[var(--radius-md)] py-2.5 transition-all duration-150 hover:brightness-110 active:scale-[0.985] cursor-pointer"
            style={{ background: "var(--accent)", color: "#FFFFFF" }}
          >
            <Check className="w-4 h-4" strokeWidth={2.5} />
            Done
          </button>
          <button
            onClick={() => onEdit(task)}
            className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-[var(--radius-md)] text-sm font-medium transition-all duration-150 cursor-pointer"
            style={{
              border: "1px solid var(--border)",
              color: "var(--muted)",
              background: "transparent",
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.background = "var(--surface)";
              (e.currentTarget as HTMLButtonElement).style.color = "var(--foreground)";
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.background = "transparent";
              (e.currentTarget as HTMLButtonElement).style.color = "var(--muted)";
            }}
          >
            Edit
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
