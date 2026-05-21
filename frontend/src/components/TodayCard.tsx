"use client"
import { useState, useEffect, useCallback } from "react"
import { api } from "@/lib/api"

interface Task {
  id: string
  title: string
  effort?: string
  importance?: number
  context?: string
  priority_index?: number
  deadline?: string
  status: string
}

interface Step {
  id: string
  title: string
  status: string
}

const EFFORT_COLORS: Record<string, string> = {
  low: "text-emerald-400 bg-emerald-400/10",
  medium: "text-amber-400 bg-amber-400/10",
  high: "text-rose-400 bg-rose-400/10",
}

export function TodayCard({ task, onComplete, onSkip }: {
  task: Task
  onComplete: () => void
  onSkip: () => void
}) {
  const [completing, setCompleting] = useState(false)
  const [skipping, setSkipping] = useState(false)
  const [why, setWhy] = useState<string | null>(null)
  const [loadingWhy, setLoadingWhy] = useState(false)
  const [steps, setSteps] = useState<Step[]>([])
  const [showSteps, setShowSteps] = useState(false)
  const [stepInput, setStepInput] = useState("")
  const [addingSteps, setAddingSteps] = useState(false)
  const effortStyle = EFFORT_COLORS[task.effort || ""] || "text-zinc-400 bg-zinc-400/10"

  const loadSteps = useCallback(async () => {
    const data = await api.getSteps(task.id)
    setSteps(data)
  }, [task.id])

  useEffect(() => {
    if (showSteps) loadSteps()
  }, [showSteps, loadSteps])

  async function handleComplete() {
    setCompleting(true)
    try { await api.completeTask(task.id); onComplete() }
    finally { setCompleting(false) }
  }

  async function handleSkip() {
    setSkipping(true)
    try { await api.rescheduleTask(task.id); onSkip() }
    finally { setSkipping(false) }
  }

  async function handleWhy() {
    if (why) { setWhy(null); return }
    setLoadingWhy(true)
    try {
      const data = await api.whyTask(task.id)
      setWhy(data.explanation)
    } finally {
      setLoadingWhy(false)
    }
  }

  async function handleAddSteps(e: React.FormEvent) {
    e.preventDefault()
    if (!stepInput.trim()) return
    setAddingSteps(true)
    try {
      const created = await api.addSteps(task.id, stepInput)
      setSteps(prev => [...prev, ...created])
      setStepInput("")
    } finally {
      setAddingSteps(false)
    }
  }

  async function handleCompleteStep(stepId: string) {
    await api.completeTask(stepId)
    setSteps(prev => prev.map(s => s.id === stepId ? { ...s, status: "completed" } : s))
  }

  return (
    <div className="relative overflow-hidden bg-gradient-to-br from-indigo-900/30 via-zinc-900 to-zinc-900 border border-indigo-800/40 rounded-3xl p-8">
      <div className="absolute -top-10 -right-10 w-40 h-40 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />

      <p className="text-xs font-semibold text-indigo-400 uppercase tracking-widest mb-5">
        🎯 Today&apos;s Focus
      </p>

      <h2 className="text-2xl font-bold text-white mb-5 leading-snug pr-4">{task.title}</h2>

      <div className="flex flex-wrap gap-2 mb-6">
        {task.effort && (
          <span className={`text-xs px-3 py-1 rounded-full font-medium ${effortStyle}`}>
            ⚡ {task.effort} effort
          </span>
        )}
        {task.context && (
          <span className="text-xs px-3 py-1 rounded-full font-medium text-zinc-400 bg-zinc-800">
            📚 {task.context}
          </span>
        )}
        {task.deadline && (
          <span className="text-xs px-3 py-1 rounded-full font-medium text-zinc-400 bg-zinc-800">
            📅 {new Date(task.deadline).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
          </span>
        )}
      </div>

      {why && (
        <div className="mb-5 px-4 py-3 bg-indigo-950/50 border border-indigo-800/30 rounded-2xl">
          <p className="text-sm text-indigo-200 leading-relaxed">{why}</p>
        </div>
      )}

      {/* Steps section */}
      {showSteps && (
        <div className="mb-5 space-y-3">
          <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">Steps</p>
          {steps.length === 0 && (
            <p className="text-xs text-zinc-600">No steps yet. Add some below.</p>
          )}
          {steps.map(step => (
            <div key={step.id} className="flex items-center gap-3">
              <button
                onClick={() => handleCompleteStep(step.id)}
                disabled={step.status === "completed"}
                className={`w-5 h-5 rounded-full border flex items-center justify-center shrink-0 transition ${
                  step.status === "completed"
                    ? "bg-emerald-600 border-emerald-600"
                    : "border-zinc-600 hover:border-indigo-400"
                }`}
              >
                {step.status === "completed" && <span className="text-white text-xs">✓</span>}
              </button>
              <span className={`text-sm ${step.status === "completed" ? "line-through text-zinc-600" : "text-zinc-300"}`}>
                {step.title}
              </span>
            </div>
          ))}
          <form onSubmit={handleAddSteps} className="flex gap-2 pt-1">
            <input
              value={stepInput}
              onChange={e => setStepInput(e.target.value)}
              placeholder="Add steps... (comma or line separated)"
              className="flex-1 bg-zinc-800 text-white text-sm rounded-xl px-3 py-2 border border-zinc-700 focus:outline-none focus:border-indigo-500 placeholder-zinc-600"
            />
            <button
              type="submit"
              disabled={addingSteps || !stepInput.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-sm font-medium transition disabled:opacity-40"
            >
              {addingSteps ? "..." : "Add"}
            </button>
          </form>
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={handleComplete}
          disabled={completing}
          className="flex-1 py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl font-semibold text-sm transition disabled:opacity-50"
        >
          {completing ? "Marking..." : "✅ Done"}
        </button>
        <button
          onClick={handleSkip}
          disabled={skipping}
          className="px-5 py-3.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-2xl font-medium text-sm transition disabled:opacity-50"
        >
          {skipping ? "..." : "⏭️ Skip"}
        </button>
        <button
          onClick={() => setShowSteps(s => !s)}
          className="px-5 py-3.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-2xl font-medium text-sm transition"
        >
          {showSteps ? "Hide" : "Steps"}
        </button>
        <button
          onClick={handleWhy}
          disabled={loadingWhy}
          className="px-5 py-3.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-2xl font-medium text-sm transition disabled:opacity-50"
        >
          {loadingWhy ? "..." : why ? "Why ✕" : "Why?"}
        </button>
      </div>
    </div>
  )
}

export function EmptyState() {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-10 text-center">
      <div className="text-5xl mb-4">🎉</div>
      <h2 className="text-xl font-bold text-white mb-2">All clear!</h2>
      <p className="text-zinc-500 text-sm">No pending tasks. Do a brain dump below to get started.</p>
    </div>
  )
}
