import type { Task } from "@/types"

type RawTask = Record<string, unknown>

export function apiEffortToTaskEffort(value: unknown): Task["effort"] {
  const s = String(value ?? "medium")
  if (s === "low" || s === "high") return s
  return "medium"
}

export function taskEffortToApiEffort(value: Task["effort"]): "low" | "medium" | "high" {
  return value
}

export function effortToHours(effort: Task["effort"]): string {
  if (effort === "low") return "1h"
  if (effort === "high") return "4h"
  return "2h"
}

export function mapApiTask(raw: RawTask, index = 0): Task {
  const rawSteps = Array.isArray(raw.steps) ? raw.steps : []
  return {
    id: String(raw.id),
    title: String(raw.title),
    effort: apiEffortToTaskEffort(raw.effort),
    deadline: raw.deadline ? String(raw.deadline) : null,
    state: (raw.status ?? "pending") as Task["state"],
    priority_score: Number(raw.priority_index ?? 0),
    is_primary: index === 0,
    notes: raw.notes ? String(raw.notes) : null,
    created_at: String(raw.created_at),
    steps: rawSteps.map((step) => ({
      id: String((step as RawTask).id),
      title: String((step as RawTask).title),
      state: (((step as RawTask).status ?? "pending") as Task["state"]),
    })),
  }
}
