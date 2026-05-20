"use client";

import { useState, useRef } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { DraggableBubbleProps, Quadrant } from "@/components/matrix/types";

const TILE_W_DESKTOP = 152;
const TILE_W_MOBILE = 116;
const TILE_H = 80;

function clamp(v: number, min: number, max: number) {
  return Math.min(Math.max(v, min), max);
}

const QUADRANT_ACCENT: Record<Quadrant, string> = {
  Q1: "border-l-rose-400",
  Q2: "border-l-blue-400",
  Q3: "border-l-slate-300",
  Q4: "border-l-amber-400",
};

// Importance badge: higher = more red
function importanceBadgeStyle(score: number): string {
  if (score >= 7) return "bg-rose-50 text-rose-600";
  if (score >= 4) return "bg-amber-50 text-amber-600";
  return "bg-slate-100 text-slate-500";
}

export function DraggableBubble({
  task,
  left,
  top,
  containerWidth,
  containerHeight,
  isCritical,
  isMobile,
  isEditing,
  onDrop,
  onTap,
}: DraggableBubbleProps) {
  const [isDragging, setIsDragging] = useState(false);
  const didDragRef = useRef(false);

  const tileW = isMobile ? TILE_W_MOBILE : TILE_W_DESKTOP;

  // left/top are center coords — offset to get top-left corner for CSS positioning
  const x = clamp(left - tileW / 2, 0, Math.max(containerWidth - tileW, 0));
  const y = clamp(top - TILE_H / 2, 0, Math.max(containerHeight - TILE_H, 0));
  const maxLeft = Math.max(containerWidth - tileW, 0);
  const maxTop = Math.max(containerHeight - TILE_H, 0);

  // Tile center (used to compute final drop coords after drag offset)
  const tileCenterX = x + tileW / 2;
  const tileCenterY = y + TILE_H / 2;

  const shouldGlow = isCritical && task.scheduledToday;
  // importance and urgency are 0–100 internally; display as 1–10
  const importanceScore = Math.max(1, Math.round(task.importance / 10));
  const urgencyScore = Math.max(1, Math.round(task.urgency / 10));
  const accentClass = QUADRANT_ACCENT[task.quadrant];
  const importanceStyle = importanceBadgeStyle(importanceScore);

  return (
    <motion.div
      className="absolute touch-none select-none"
      style={{
        left: x,
        top: y,
        width: tileW,
        zIndex: isDragging ? 50 : shouldGlow ? 30 : 10,
      }}
      drag={isEditing && !isMobile}
      dragElastic={0}
      dragMomentum={false}
      dragConstraints={{
        left: -x,
        right: maxLeft - x,
        top: -y,
        bottom: maxTop - y,
      }}
      onDragStart={() => {
        setIsDragging(true);
        didDragRef.current = false;
      }}
      onDragEnd={(_, info) => {
        setIsDragging(false);
        if (Math.abs(info.offset.x) > 3 || Math.abs(info.offset.y) > 3) {
          didDragRef.current = true;
        }
        const finalCX = tileCenterX + info.offset.x;
        const finalCY = tileCenterY + info.offset.y;
        onDrop(task.id, finalCX, finalCY);
      }}
      onTap={() => {
        if (didDragRef.current) {
          didDragRef.current = false;
          return;
        }
        onTap(task.id);
      }}
      whileTap={{ scale: isMobile ? 0.95 : 0.98 }}
      animate={
        isDragging
          ? { rotate: 1.5, scale: 1.02 }
          : { rotate: 0, scale: 1 }
      }
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      aria-label={`${task.title}, importance ${importanceScore}, urgency ${urgencyScore}, ${task.quadrant}`}
    >
      <div
        className={cn(
          "relative w-full rounded-xl border border-l-2 border-gray-200 bg-white px-3 py-2.5 transition-all duration-150",
          accentClass,
          isEditing ? "cursor-grab active:cursor-grabbing" : "cursor-pointer",
          shouldGlow && "ring-2 ring-emerald-200/70",
          isDragging
            ? "shadow-xl opacity-90"
            : "shadow-sm hover:shadow-md hover:-translate-y-0.5"
        )}
      >
        <p className="line-clamp-2 text-sm font-semibold leading-snug text-gray-900">
          {task.title}
        </p>

        <div className="mt-2 flex flex-wrap items-center gap-1">
          <span className={cn("rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums", importanceStyle)}>
            🔥 {importanceScore}
          </span>
          <span className="rounded-full bg-sky-50 px-1.5 py-0.5 text-[10px] font-semibold tabular-nums text-sky-600">
            ⚡ {urgencyScore}
          </span>
          {task.scheduledToday && (
            <span className="rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
              Today
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}
