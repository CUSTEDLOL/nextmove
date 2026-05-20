"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MappedTask, Quadrant } from "@/components/matrix/types";
import { TimeEstimatePicker } from "@/components/shared/TimeEstimatePicker";
import { matrixEffortToApiEffort, apiEffortToMatrixEffort } from "@/lib/matrix";

const MODAL_W = 320;
const MODAL_H_APPROX = 540; // slight overestimate so clamping always keeps modal in viewport
const GAP = 10;

type TaskEditPanelProps = {
  task: MappedTask;
  anchor: { x: number; y: number }; // screen-space center of the tile
  tileW: number;
  onSave: (taskId: string, updates: { title: string; effort: 1 | 2 | 3; quadrant: Quadrant }) => void;
  onClose: () => void;
};

// Order matches the canvas: Q2 top-left, Q1 top-right, Q3 bottom-left, Q4 bottom-right
const QUADRANT_OPTIONS: {
  id: Quadrant;
  label: string;
  sub: string;
  accent: string;
  ring: string;
  bg: string;
  badge: string;
}[] = [
  { id: "Q2", label: "Priority for Later", sub: "important, not yet urgent", accent: "border-blue-400",  ring: "ring-blue-200",  bg: "bg-blue-50/80",  badge: "border-blue-200 bg-blue-50 text-blue-700"     },
  { id: "Q1", label: "Do First",          sub: "urgent + important",        accent: "border-rose-400",  ring: "ring-rose-200",  bg: "bg-rose-50/80",  badge: "border-rose-200 bg-rose-50 text-rose-700"     },
  { id: "Q3", label: "Low Priority",      sub: "if there's time",           accent: "border-slate-300", ring: "ring-slate-200", bg: "bg-slate-50/80", badge: "border-slate-200 bg-slate-100 text-slate-600" },
  { id: "Q4", label: "Quick Tasks",       sub: "urgent but low-stakes",     accent: "border-amber-400", ring: "ring-amber-200", bg: "bg-amber-50/80", badge: "border-amber-200 bg-amber-50 text-amber-700"  },
];


export function TaskEditPanel({ task, anchor, tileW, onSave, onClose }: TaskEditPanelProps) {
  const [title, setTitle] = useState(task.title);
  const [effort, setEffort] = useState<1 | 2 | 3>(task.effort);
  const [quadrant, setQuadrant] = useState<Quadrant>(task.quadrant);

  // Compute modal position anchored to the tile
  const vpW = typeof window !== "undefined" ? window.innerWidth : 1200;
  const vpH = typeof window !== "undefined" ? window.innerHeight : 800;

  const tileHalfW = tileW / 2;

  // Prefer right of tile; flip left if it would overflow
  const rightAttempt = anchor.x + tileHalfW + GAP;
  const fitsRight = rightAttempt + MODAL_W <= vpW - 8;
  const left = fitsRight
    ? rightAttempt
    : Math.max(8, anchor.x - tileHalfW - GAP - MODAL_W);

  // Center vertically with the tile, clamped to viewport
  const top = Math.max(8, Math.min(anchor.y - MODAL_H_APPROX / 2, vpH - MODAL_H_APPROX - 8));

  const transformOrigin = fitsRight ? "left center" : "right center";
  const currentQ = QUADRANT_OPTIONS.find((q) => q.id === quadrant)!;

  return (
    <motion.div
      className="fixed z-50 flex flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl max-h-[calc(100vh-16px)] overflow-y-auto"
      style={{ left, top, width: MODAL_W, transformOrigin }}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ type: "spring", stiffness: 420, damping: 30 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <span className={cn("text-[10px] font-bold uppercase tracking-[0.2em] px-2.5 py-1 rounded-full border", currentQ.badge)}>
          {currentQ.id} · {currentQ.label}
        </span>
        <button
          onClick={onClose}
          className="rounded-full p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          aria-label="Close"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Body */}
      <div className="px-4 py-4 space-y-4">

        {/* Title */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-semibold uppercase tracking-[0.2em] text-gray-400">
            Task
          </label>
          <textarea
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            rows={3}
            className="w-full resize-none rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 text-sm font-medium text-gray-900 placeholder:text-gray-400 focus:border-gray-400 focus:bg-white focus:outline-none transition-colors"
            placeholder="Task title…"
          />
        </div>

        {/* Time estimate */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-semibold uppercase tracking-[0.2em] text-gray-400">
            Time estimate
          </label>
          <TimeEstimatePicker
            value={matrixEffortToApiEffort(effort)}
            onChange={(v) => setEffort(apiEffortToMatrixEffort(v))}
          />
        </div>

        {/* Quadrant */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-semibold uppercase tracking-[0.2em] text-gray-400">
            Quadrant
          </label>
          <div className="grid grid-cols-2 gap-1.5">
            {QUADRANT_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                onClick={() => setQuadrant(opt.id)}
                className={cn(
                  "rounded-xl border-2 px-3 py-2.5 text-left transition-all",
                  quadrant === opt.id
                    ? cn(opt.accent, opt.bg, "ring-2", opt.ring)
                    : "border-gray-100 bg-white hover:border-gray-200 hover:bg-gray-50"
                )}
              >
                <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-400">{opt.id}</p>
                <p className="text-[11px] font-bold text-gray-900 mt-0.5">{opt.label}</p>
                <p className="text-[10px] text-gray-400 mt-0.5 leading-snug">{opt.sub}</p>
              </button>
            ))}
          </div>
        </div>

      </div>

      {/* Footer */}
      <div className="flex gap-2 px-4 py-3 border-t border-gray-100">
        <button
          onClick={onClose}
          className="flex-1 rounded-xl border border-gray-200 py-2 text-sm font-medium text-gray-500 hover:bg-gray-50 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={() =>
            onSave(task.id, {
              title: title.trim() || task.title,
              effort,
              quadrant,
            })
          }
          className="flex-1 rounded-xl bg-gray-900 py-2 text-sm font-semibold text-white hover:bg-gray-700 transition-colors"
        >
          Save
        </button>
      </div>
    </motion.div>
  );
}
