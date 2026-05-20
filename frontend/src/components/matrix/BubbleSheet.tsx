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
  { quadrant: "Q1", label: "Do First",          sub: "Urgent + Important",       dot: "bg-emerald-400", bg: "bg-emerald-50/70 border-emerald-200 hover:bg-emerald-100", text: "text-emerald-700", ring: "ring-emerald-400" },
  { quadrant: "Q2", label: "Priority for Later", sub: "Important, not yet urgent", dot: "bg-blue-400",   bg: "bg-blue-50/70 border-blue-200 hover:bg-blue-100",          text: "text-blue-700",    ring: "ring-blue-400"   },
  { quadrant: "Q3", label: "Low Priority",       sub: "If there's time",           dot: "bg-slate-300",  bg: "bg-slate-50/70 border-slate-200 hover:bg-slate-100",       text: "text-slate-600",   ring: "ring-slate-300"  },
  { quadrant: "Q4", label: "Quick Tasks",        sub: "Urgent but low-stakes",     dot: "bg-amber-400",  bg: "bg-amber-50/70 border-amber-200 hover:bg-amber-100",       text: "text-amber-700",   ring: "ring-amber-400"  },
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
