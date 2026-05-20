import type { MappedTask, Quadrant } from "@/components/matrix/types"

export const MATRIX_VISIBLE_LIMIT = 12

function clampScore(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)))
}

export function quadrantFromScores(urgency: number, importance: number): Quadrant {
  if (urgency >= 50 && importance >= 50) return "Q1"
  if (urgency < 50 && importance >= 50) return "Q2"
  if (urgency < 50 && importance < 50) return "Q3"
  return "Q4"
}

export function quadrantCenter(quadrant: Quadrant): { urgency: number; importance: number } {
  if (quadrant === "Q1") return { urgency: 75, importance: 75 }
  if (quadrant === "Q2") return { urgency: 25, importance: 75 }
  if (quadrant === "Q3") return { urgency: 25, importance: 25 }
  return { urgency: 75, importance: 25 }
}

export function apiEffortToMatrixEffort(value: unknown): 1 | 2 | 3 {
  const effort = String(value ?? "medium")
  if (effort === "low") return 1
  if (effort === "high") return 3
  return 2
}

export function matrixEffortToApiEffort(value: 1 | 2 | 3): "low" | "medium" | "high" {
  if (value === 1) return "low"
  if (value === 3) return "high"
  return "medium"
}

// Importance weighted higher than urgency so the Eisenhower order holds:
// Q1 (urgent+important) > Q2 (important) > Q4 (urgent) > Q3 (neither)
// Effort adds a small tiebreaker (max 4 pts) that never flips quadrant order.
export function matrixPriorityScore(urgency: number, importance: number, effort: 1 | 2 | 3): number {
  return clampScore(urgency * 0.35 + importance * 0.55 + (effort - 1) * 2)
}

// Quadrant rank offsets that guarantee Q1 > Q2 > Q4 > Q3 regardless of individual scores
const Q_RANK: Record<Quadrant, number> = { Q1: 3000, Q2: 2000, Q4: 1000, Q3: 0 }

export function matrixTopTask(tasks: MappedTask[]): MappedTask | undefined {
  return [...tasks].sort(
    (a, b) => (Q_RANK[b.quadrant] + b.priorityScore) - (Q_RANK[a.quadrant] + a.priorityScore)
  )[0]
}

export function mapApiTaskToMatrixTask(raw: Record<string, unknown>): MappedTask {
  const urgency = clampScore(Number(raw.urgency_score ?? 50))
  const importance = clampScore(Number(raw.importance_score ?? 50))
  const effort = apiEffortToMatrixEffort(raw.effort)
  return {
    id: String(raw.id),
    title: String(raw.title),
    urgency,
    importance,
    priorityScore: clampScore(Number(raw.priority_index ?? matrixPriorityScore(urgency, importance, effort)) * 10),
    effort,
    scheduledToday: Boolean(raw.scheduled_today),
    quadrant: quadrantFromScores(urgency, importance),
  }
}

export function selectMatrixTasks(
  tasks: MappedTask[],
  query: string,
  filter: "all" | "scheduled" | "unscheduled",
  limit = MATRIX_VISIBLE_LIMIT,
) {
  const normalizedQuery = query.trim().toLowerCase()
  const filtered = tasks
    .filter((task) => {
      if (filter === "scheduled" && !task.scheduledToday) return false
      if (filter === "unscheduled" && task.scheduledToday) return false
      if (!normalizedQuery) return true
      return task.title.toLowerCase().includes(normalizedQuery)
    })
    .sort((a, b) => {
      if (a.scheduledToday !== b.scheduledToday) return a.scheduledToday ? -1 : 1
      return b.priorityScore - a.priorityScore
    })

  return {
    filtered,
    visible: filtered.slice(0, limit),
    overflow: filtered.slice(limit),
  }
}
