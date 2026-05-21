"use client"

import { cn } from "@/lib/utils"

type Effort = "low" | "medium" | "high"

const OPTIONS: { value: Effort; label: string }[] = [
  { value: "low",    label: "1h" },
  { value: "medium", label: "2h" },
  { value: "high",   label: "4h" },
]

const ACTIVE: Record<Effort, string> = {
  low:    "border-sky-400 bg-sky-50 text-sky-700",
  medium: "border-amber-400 bg-amber-50 text-amber-700",
  high:   "border-rose-400 bg-rose-50 text-rose-600",
}

interface TimeEstimatePickerProps {
  value: Effort
  onChange: (v: Effort) => void
  className?: string
}

export function TimeEstimatePicker({ value, onChange, className }: TimeEstimatePickerProps) {
  return (
    <div className={cn("grid grid-cols-3 gap-1.5", className)}>
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            "rounded-xl border py-2 text-xs font-semibold transition-all",
            value === opt.value
              ? ACTIVE[opt.value]
              : "border-gray-200 text-gray-500 hover:bg-gray-50"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
