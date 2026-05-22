"use client"

import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { AppLayout } from "@/components/layout/AppLayout"
import { useSchedule, type Block } from "@/lib/schedule-store"
import {
  addDays,
  dayKey,
  fmtHour,
  fmtMonthDay,
  fmtTime,
  minsFromHourStart,
  parseLocal,
  pxFromMins,
  sameDay,
  snapToInterval,
  startOfDay,
  toLocalInputValue,
  localInputToUtc,
} from "@/lib/calendar-utils"
import { api } from "@/lib/api"
import { Plus, RefreshCw } from "lucide-react"

type View = "day" | "week" | "month"

const HOUR_PX = 72
const HOUR_START = 7
const HOUR_END = 23
const TOTAL_HOURS = HOUR_END - HOUR_START
const SNAP_MINS = 15

const BLOCK_COLORS: Record<Block["entry_type"], string> = {
  block:    "bg-blue-600 text-white",
  deadline: "bg-red-600 text-white",
  prep:     "bg-gray-400 text-white border-dashed",
  event:    "bg-amber-500 text-white",
}

const BLOCK_ACCENT: Record<Block["entry_type"], string> = {
  block:    "bg-blue-400",
  deadline: "bg-red-400",
  prep:     "bg-gray-300",
  event:    "bg-amber-300",
}

const BLOCK_TEXT: Record<Block["entry_type"], string> = {
  block:    "text-blue-600",
  deadline: "text-red-600",
  prep:     "text-gray-500",
  event:    "text-amber-600",
}

// ─── Column overlap layout ────────────────────────────────────────────────────

function assignColumns(blocks: Block[]): { block: Block; col: number; totalCols: number }[] {
  const sorted = [...blocks].sort(
    (a, b) => parseLocal(a.start_time).getTime() - parseLocal(b.start_time).getTime()
  )
  const cols: { block: Block; col: number; end: Date }[] = []
  const result: { block: Block; col: number; totalCols: number }[] = []

  for (const b of sorted) {
    const start = parseLocal(b.start_time)
    const end = parseLocal(b.end_time)
    let col = 0
    while (cols[col] && cols[col].end > start) col++
    cols[col] = { block: b, col, end }
    result.push({ block: b, col, totalCols: 0 })
  }

  for (let i = 0; i < result.length; i++) {
    const start = parseLocal(result[i].block.start_time)
    const end = parseLocal(result[i].block.end_time)
    let maxCol = result[i].col
    for (let j = 0; j < result.length; j++) {
      const s2 = parseLocal(result[j].block.start_time)
      const e2 = parseLocal(result[j].block.end_time)
      if (s2 < end && e2 > start) maxCol = Math.max(maxCol, result[j].col)
    }
    result[i].totalCols = maxCol + 1
  }
  return result
}

// ─── Event tile ───────────────────────────────────────────────────────────────

interface TileProps {
  block: Block
  col: number
  totalCols: number
  onDragStart: (block: Block, offsetY: number) => void
}

function EventTile({ block, col, totalCols, onDragStart }: TileProps) {
  const start = parseLocal(block.start_time)
  const end = parseLocal(block.end_time)
  const startMins = Math.max(0, minsFromHourStart(start, HOUR_START))
  const rawDur = block.entry_type === "deadline" ? 30 : (end.getTime() - start.getTime()) / 60000
  const durMins = Math.min(rawDur, TOTAL_HOURS * 60 - startMins)
  const topPx = pxFromMins(startMins, HOUR_PX)
  const heightPx = Math.max(pxFromMins(durMins, HOUR_PX), 28)
  const colW = 100 / totalCols
  const isShort = heightPx < 40

  return (
    <div
      className={`absolute rounded-lg overflow-hidden select-none hover:brightness-90 transition-all ${BLOCK_COLORS[block.entry_type]} ${block.entry_type === "event" ? "cursor-grab active:cursor-grabbing" : "cursor-pointer"}`}
      style={{
        top: topPx,
        height: heightPx,
        left: `${col * colW + 0.5}%`,
        width: `${colW - 1}%`,
        zIndex: 10,
        minHeight: 28,
      }}
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => {
        e.stopPropagation()
        const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
        onDragStart(block, e.clientY - rect.top)
      }}
    >
      <div className="px-2 py-1 h-full flex flex-col justify-start overflow-hidden">
        <p className={`font-semibold leading-tight truncate ${isShort ? "text-[11px]" : "text-xs"}`}>
          {block.task_title}
        </p>
        {!isShort && (
          <p className="text-[10px] opacity-75 mt-0.5">
            {fmtTime(start)} – {fmtTime(end)}
          </p>
        )}
      </div>
    </div>
  )
}

// ─── Time grid (day + week) ───────────────────────────────────────────────────

interface TimeGridProps {
  days: Date[]
  blocks: Block[]
  onClickSlot: (day: Date, minutesFromStart: number) => void
  onDragStart: (block: Block, offsetY: number) => void
}

function TimeGrid({ days, blocks, onClickSlot, onDragStart }: TimeGridProps) {
  const now = new Date()
  const nowMins = minsFromHourStart(now, HOUR_START)
  const nowPx = pxFromMins(nowMins, HOUR_PX)
  const isNowVisible = nowMins >= 0 && nowMins <= TOTAL_HOURS * 60

  const blocksByDay: Record<string, Block[]> = {}
  for (const b of blocks) {
    const k = dayKey(parseLocal(b.start_time))
    if (!blocksByDay[k]) blocksByDay[k] = []
    blocksByDay[k].push(b)
  }

  const totalHeight = TOTAL_HOURS * HOUR_PX

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      {/* Gutter */}
      <div className="shrink-0 w-14 flex flex-col" style={{ paddingTop: 33 }}>
        <div className="relative" style={{ height: totalHeight }}>
          {Array.from({ length: TOTAL_HOURS }, (_, i) => (
            <div
              key={i}
              className="absolute w-full flex justify-end pr-2"
              style={{ top: i * HOUR_PX - 8 }}
            >
              <span className="text-xs font-medium text-gray-500">{fmtHour(HOUR_START + i)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Day columns — scrollable vertically */}
      <div className="flex-1 overflow-y-auto min-w-0">
        {/* Day headers — sticky */}
        <div
          className="sticky top-0 z-20 bg-white border-b border-gray-200 grid"
          style={{ gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))` }}
        >
          {days.map((day) => {
            const isToday = sameDay(day, now)
            return (
              <div key={dayKey(day)} className="flex items-center justify-center py-2 border-l border-gray-100">
                <span
                  className={`text-xs font-bold px-2.5 py-1 rounded-full ${
                    isToday ? "bg-blue-600 text-white" : "text-gray-600"
                  }`}
                >
                  {day.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
                </span>
              </div>
            )
          })}
        </div>

        {/* Grid body */}
        <div
          className="relative grid"
          style={{
            gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))`,
            height: totalHeight,
          }}
        >
          {/* Hour lines across all columns */}
          <div className="absolute inset-0 pointer-events-none">
            {/* Hour lines */}
            {Array.from({ length: TOTAL_HOURS }, (_, i) => (
              <div
                key={i}
                className="absolute w-full border-t border-gray-200"
                style={{ top: i * HOUR_PX }}
              />
            ))}
            {/* 30-min sub-lines */}
            {Array.from({ length: TOTAL_HOURS }, (_, i) => (
              <div
                key={`half-${i}`}
                className="absolute w-full border-t border-gray-100"
                style={{ top: i * HOUR_PX + HOUR_PX / 2 }}
              />
            ))}
          </div>

          {days.map((day) => {
            const isToday = sameDay(day, now)
            const dayBlocks = blocksByDay[dayKey(day)] ?? []
            const positioned = assignColumns(dayBlocks)

            return (
              <div
                key={dayKey(day)}
                className="relative border-l border-gray-100 cursor-pointer"
                onClick={(e) => {
                  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
                  const rawMins = ((e.clientY - rect.top) / HOUR_PX) * 60
                  const snapped = snapToInterval(Math.round(rawMins), SNAP_MINS)
                  onClickSlot(day, snapped)
                }}
              >
                {/* Current time indicator */}
                {isToday && isNowVisible && (
                  <div
                    className="absolute w-full z-20 flex items-center pointer-events-none"
                    style={{ top: nowPx }}
                  >
                    <div className="w-3 h-3 rounded-full bg-emerald-500 -ml-1.5 shrink-0" />
                    <div className="flex-1 h-[2px] bg-emerald-500" />
                  </div>
                )}

                {positioned.map(({ block, col, totalCols }) => (
                  <EventTile
                    key={block.id}
                    block={block}
                    col={col}
                    totalCols={totalCols}
                    onDragStart={onDragStart}
                  />
                ))}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ─── Month grid ───────────────────────────────────────────────────────────────

function MonthGrid({
  anchor,
  blocks,
  onDayClick,
  onBlockClick,
  onCreateClick,
}: {
  anchor: Date
  blocks: Block[]
  onDayClick: (day: Date) => void
  onBlockClick: (block: Block, x: number, y: number) => void
  onCreateClick: (day: Date) => void
}) {
  const year = anchor.getFullYear()
  const month = anchor.getMonth()
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  const startPad = firstDay.getDay()
  const cells: (Date | null)[] = [
    ...Array(startPad).fill(null),
    ...Array.from({ length: lastDay.getDate() }, (_, i) => new Date(year, month, i + 1)),
  ]
  while (cells.length % 7 !== 0) cells.push(null)

  const blocksByDay: Record<string, Block[]> = {}
  for (const b of blocks) {
    const k = dayKey(parseLocal(b.start_time))
    if (!blocksByDay[k]) blocksByDay[k] = []
    blocksByDay[k].push(b)
  }

  return (
    <div className="h-full flex flex-col">
      <div className="grid grid-cols-7 border-b border-gray-200 shrink-0">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
          <div key={d} className="text-center text-xs font-medium text-gray-400 py-2">
            {d}
          </div>
        ))}
      </div>
      <div className="flex-1 grid grid-cols-7 gap-px bg-gray-200 overflow-auto">
        {cells.map((day, i) => {
          if (!day) return <div key={i} className="bg-gray-50" />
          const isToday = sameDay(day, new Date())
          const dayBlocks = blocksByDay[dayKey(day)] ?? []
          return (
            <div
              key={i}
              className="bg-white p-1.5 overflow-hidden hover:bg-gray-50 transition-colors cursor-pointer"
              onClick={() => onCreateClick(day)}
            >
              {/* Clicking the date number navigates to day view */}
              <p
                className={`text-xs font-semibold w-6 h-6 flex items-center justify-center rounded-full mb-1 cursor-pointer ${
                  isToday ? "bg-emerald-500 text-white" : "text-gray-500 hover:bg-gray-100"
                }`}
                onClick={(e) => { e.stopPropagation(); onDayClick(day) }}
              >
                {day.getDate()}
              </p>
              <div className="space-y-0.5">
                {dayBlocks.slice(0, 3).map((b) => (
                  <div
                    key={b.id}
                    className={`text-[10px] px-1.5 py-0.5 rounded flex items-center gap-1 truncate cursor-pointer hover:brightness-90 transition-all ${BLOCK_COLORS[b.entry_type]}`}
                    title={b.task_title}
                    onClick={(e) => { e.stopPropagation(); onBlockClick(b, e.clientX, e.clientY) }}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${BLOCK_ACCENT[b.entry_type]}`} />
                    {fmtTime(parseLocal(b.start_time)).replace(":00 ", " ")} {b.task_title}
                  </div>
                ))}
                {dayBlocks.length > 3 && (
                  <p
                    className="text-[10px] text-gray-400 pl-1 cursor-pointer hover:text-gray-600"
                    onClick={() => onDayClick(day)}
                  >
                    +{dayBlocks.length - 3} more
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Create event popover ─────────────────────────────────────────────────────

interface CreatePopoverProps {
  initialDay: Date
  initialMinsFromStart: number
  onSave: (title: string, startUtc: string, endUtc: string) => Promise<void>
  onClose: () => void
}

function CreatePopover({ initialDay, initialMinsFromStart, onSave, onClose }: CreatePopoverProps) {
  const startDate = new Date(initialDay)
  startDate.setHours(HOUR_START, 0, 0, 0)
  startDate.setMinutes(initialMinsFromStart)
  const endDate = new Date(startDate.getTime() + 60 * 60 * 1000) // +1 hour

  const [title, setTitle] = useState("")
  const [startVal, setStartVal] = useState(toLocalInputValue(startDate))
  const [endVal, setEndVal] = useState(toLocalInputValue(endDate))
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    if (!title.trim()) return
    setSaving(true)
    await onSave(title.trim(), localInputToUtc(startVal), localInputToUtc(endVal))
    setSaving(false)
  }

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-30" onClick={onClose} />
      {/* Popover */}
      <div className="fixed z-40 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-2xl border border-gray-200 shadow-xl p-5 w-[min(20rem,90vw)] max-h-[90dvh] overflow-y-auto">
        <p className="text-sm font-semibold text-gray-900 mb-3">New event</p>
        <input
          autoFocus
          type="text"
          placeholder="Event title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSave()}
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-emerald-400 mb-2"
        />
        <div className="flex flex-col gap-2 mb-3">
          <div>
            <label className="text-[10px] font-medium text-gray-400 uppercase tracking-wide">Start</label>
            <input
              type="datetime-local"
              value={startVal}
              onChange={(e) => setStartVal(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-xs outline-none focus:border-emerald-400 mt-0.5"
            />
          </div>
          <div>
            <label className="text-[10px] font-medium text-gray-400 uppercase tracking-wide">End</label>
            <input
              type="datetime-local"
              value={endVal}
              onChange={(e) => setEndVal(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-xs outline-none focus:border-emerald-400 mt-0.5"
            />
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 rounded-lg">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !title.trim()}
            className="px-3 py-1.5 text-xs bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </>
  )
}

// ─── Drag ghost overlay ───────────────────────────────────────────────────────

interface DragState {
  block: Block
  offsetY: number       // px offset within the tile where drag started
  currentY: number      // current mouse Y relative to viewport
  columnEl: HTMLElement | null
}

// ─── Block edit / detail popover ─────────────────────────────────────────────

const POPOVER_W = 300
const POPOVER_H = 220  // approximate — enough to clamp

function BlockEditModal({
  block,
  anchorX,
  anchorY,
  onClose,
  onSaveEvent,
  onDeleteEvent,
  onCompleteTask,
}: {
  block: Block
  anchorX: number
  anchorY: number
  onClose: () => void
  onSaveEvent: (id: string, title: string, startUtc: string, endUtc: string) => Promise<void>
  onDeleteEvent: (id: string) => Promise<void>
  onCompleteTask: (id: string) => Promise<void>
}) {
  const start = parseLocal(block.start_time)
  const end = parseLocal(block.end_time)
  const isEvent = block.entry_type === "event"
  const eventId = isEvent ? block.id.replace("event-", "") : ""

  const [title, setTitle] = useState(block.task_title)
  const [startVal, setStartVal] = useState(toLocalInputValue(start))
  const [endVal, setEndVal] = useState(toLocalInputValue(end))
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [completing, setCompleting] = useState(false)

  const typeLabel: Record<Block["entry_type"], string> = {
    block: "Task block",
    deadline: "Deadline",
    prep: "Prep block",
    event: "Event",
  }

  // Position near click, clamped to viewport
  const vw = typeof window !== "undefined" ? window.innerWidth : 1200
  const vh = typeof window !== "undefined" ? window.innerHeight : 800
  const GAP = 8
  let left = anchorX + GAP
  let top = anchorY - POPOVER_H / 2
  if (left + POPOVER_W > vw - GAP) left = anchorX - POPOVER_W - GAP
  if (left < GAP) left = GAP
  if (top + POPOVER_H > vh - GAP) top = vh - POPOVER_H - GAP
  if (top < GAP) top = GAP

  async function handleSave() {
    if (!title.trim() || !isEvent) return
    setSaving(true)
    await onSaveEvent(eventId, title.trim(), localInputToUtc(startVal), localInputToUtc(endVal))
    setSaving(false)
    onClose()
  }

  async function handleDelete() {
    if (!isEvent) return
    setDeleting(true)
    await onDeleteEvent(eventId)
    setDeleting(false)
    onClose()
  }

  async function handleComplete() {
    setCompleting(true)
    await onCompleteTask(block.id)
    setCompleting(false)
    onClose()
  }

  return createPortal(
    <>
      <div className="fixed inset-0 z-[9998]" onClick={onClose} />

      <div
        className="fixed z-[9999] bg-white rounded-2xl border border-gray-200 shadow-2xl p-4"
        style={{ left, top, width: POPOVER_W }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="flex items-center gap-2 min-w-0">
            <span className={`shrink-0 inline-block w-2.5 h-2.5 rounded-full ${BLOCK_COLORS[block.entry_type].split(" ")[0]}`} />
            <span className={`text-[10px] font-bold uppercase tracking-wide ${BLOCK_TEXT[block.entry_type]}`}>
              {typeLabel[block.entry_type]}
            </span>
          </div>
          <button onClick={onClose} className="shrink-0 text-gray-300 hover:text-gray-600 text-lg leading-none transition-colors">×</button>
        </div>

        {isEvent ? (
          /* ── Editable event fields ── */
          <div className="space-y-2">
            <input
              autoFocus
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-900 outline-none focus:border-emerald-400"
            />
            <div className="flex flex-col gap-1.5">
              <div>
                <label className="text-[10px] font-medium text-gray-400 uppercase tracking-wide">Start</label>
                <input
                  type="datetime-local"
                  value={startVal}
                  onChange={(e) => setStartVal(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 px-2 py-1 text-xs outline-none focus:border-emerald-400 mt-0.5"
                />
              </div>
              <div>
                <label className="text-[10px] font-medium text-gray-400 uppercase tracking-wide">End</label>
                <input
                  type="datetime-local"
                  value={endVal}
                  onChange={(e) => setEndVal(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 px-2 py-1 text-xs outline-none focus:border-emerald-400 mt-0.5"
                />
              </div>
            </div>
            <div className="flex items-center justify-between pt-1">
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="text-xs text-red-500 hover:text-red-700 font-medium disabled:opacity-50 transition-colors"
              >
                {deleting ? "Deleting…" : "Delete event"}
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !title.trim()}
                className="px-3 py-1.5 text-xs bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium disabled:opacity-50 transition-colors"
              >
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        ) : (
          /* ── Task block info + actions ── */
          <div>
            <p className="text-sm font-semibold text-gray-900 leading-snug mb-2 line-clamp-2">{block.task_title}</p>
            <div className="flex items-baseline gap-1.5 text-xs text-gray-600 mb-0.5">
              <span className="font-semibold text-gray-800">{fmtTime(start)}</span>
              <span className="text-gray-400">–</span>
              <span className="font-semibold text-gray-800">{fmtTime(end)}</span>
            </div>
            <p className="text-[11px] text-gray-400 mb-3">
              {start.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
            </p>
            {block.effort && (
              <p className="text-[11px] text-gray-400 mb-3">
                Effort: <span className="text-gray-700 font-medium capitalize">{block.effort}</span>
              </p>
            )}
            {block.entry_type === "block" && (
              <button
                onClick={handleComplete}
                disabled={completing}
                className="w-full px-3 py-1.5 text-xs bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium disabled:opacity-50 transition-colors"
              >
                {completing ? "Marking done…" : "Mark complete"}
              </button>
            )}
          </div>
        )}
      </div>
    </>,
    document.body
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function CalendarPage() {
  return (
    <AppLayout>
      <CalendarContent />
    </AppLayout>
  )
}

function CalendarContent() {
  const { blocks, loading, refresh, forceRefresh, rebuildAndRefresh } = useSchedule()
  const [view, setView] = useState<View>(() => {
    if (typeof window !== "undefined") {
      const s = localStorage.getItem("calendar_view")
      if (s === "day" || s === "week" || s === "month") return s as View
    }
    return "day"
  })
  const [anchor, setAnchor] = useState(startOfDay(new Date()))
  const [createSlot, setCreateSlot] = useState<{ day: Date; minsFromStart: number } | null>(null)
  const [drag, setDrag] = useState<DragState | null>(null)
  const [rebuilding, setRebuilding] = useState(false)
  const [selectedBlock, setSelectedBlock] = useState<{ block: Block; x: number; y: number } | null>(null)
  const gridRef = useRef<HTMLDivElement>(null)

  // Force-refresh on mount and whenever the user navigates back to this tab
  useEffect(() => {
    forceRefresh()
    const handler = () => { if (!document.hidden) forceRefresh() }
    document.addEventListener("visibilitychange", handler)
    return () => document.removeEventListener("visibilitychange", handler)
  }, [forceRefresh])

  // Suppress unused warning — drag state is set but ghost rendering is future work
  void drag

  // Navigation
  function nav(dir: 1 | -1) {
    setAnchor((prev) => {
      if (view === "day") return addDays(prev, dir)
      if (view === "week") return addDays(prev, dir * 7)
      const d = new Date(prev)
      d.setMonth(d.getMonth() + dir)
      return startOfDay(d)
    })
  }

  // Days in view
  let days: Date[] = []
  if (view === "day") {
    days = [anchor]
  } else if (view === "week") {
    const sunday = addDays(anchor, -anchor.getDay())
    days = Array.from({ length: 7 }, (_, i) => addDays(sunday, i))
  }

  // Filter blocks to current view window
  const visibleBlocks = blocks.filter((b) => {
    const d = parseLocal(b.start_time)
    if (view === "day") return sameDay(d, anchor)
    if (view === "week") return days.some((day) => sameDay(d, day))
    return d.getMonth() === anchor.getMonth() && d.getFullYear() === anchor.getFullYear()
  })

  // Header label
  let headerLabel = ""
  if (view === "day") headerLabel = anchor.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })
  else if (view === "week") headerLabel = `${fmtMonthDay(days[0])} – ${fmtMonthDay(days[6])}`
  else headerLabel = anchor.toLocaleDateString("en-US", { month: "long", year: "numeric" })

  // Click-to-create handler
  function handleClickSlot(day: Date, minsFromStart: number) {
    setCreateSlot({ day, minsFromStart })
  }

  async function handleCreateEvent(title: string, startUtc: string, endUtc: string) {
    await api.createCalendarEvent({ title, start_time: startUtc, end_time: endUtc })
    setCreateSlot(null)
    await forceRefresh()
  }

  async function handleSaveEvent(id: string, title: string, startUtc: string, endUtc: string) {
    await api.updateCalendarEvent(id, { title, start_time: startUtc, end_time: endUtc })
    await forceRefresh()
  }

  async function handleDeleteEvent(id: string) {
    await api.deleteCalendarEvent(id)
    await forceRefresh()
  }

  async function handleCompleteTask(blockId: string) {
    const block = blocks.find((b) => b.id === blockId)
    const taskId = block?.task_id
    if (!taskId) return
    await api.completeTask(taskId)
    await rebuildAndRefresh()
  }

  // Drag-to-reschedule handlers (only for calendar events, not task blocks)
  function handleDragStart(block: Block, offsetY: number) {
    // Task blocks are auto-managed by the scheduler — only events are manually draggable
    if (block.entry_type !== "event") {
      // Treat as a tap to open the detail modal
      setSelectedBlock({ block, x: 0, y: 0 })
      return
    }

    let hasMoved = false
    setDrag({ block, offsetY, currentY: 0, columnEl: null })

    function onMouseMove(e: MouseEvent) {
      hasMoved = true
      setDrag((prev) => prev ? { ...prev, currentY: e.clientY } : null)
    }

    async function onMouseUp(e: MouseEvent) {
      window.removeEventListener("mousemove", onMouseMove)
      window.removeEventListener("mouseup", onMouseUp)

      if (!hasMoved) {
        setDrag(null)
        setSelectedBlock({ block, x: e.clientX, y: e.clientY })
        return
      }

      setDrag((d) => {
        if (!d || !gridRef.current) return null
        const gridRect = gridRef.current.getBoundingClientRect()
        const relY = e.clientY - gridRect.top - d.offsetY
        const rawMins = (relY / HOUR_PX) * 60
        const snappedMins = snapToInterval(Math.max(0, Math.round(rawMins)), SNAP_MINS)
        const origStart = parseLocal(d.block.start_time)
        const origEnd = parseLocal(d.block.end_time)
        const durMins = (origEnd.getTime() - origStart.getTime()) / 60000

        const newStart = new Date(anchor)
        newStart.setHours(HOUR_START, 0, 0, 0)
        newStart.setMinutes(snappedMins)
        const newEnd = new Date(newStart.getTime() + durMins * 60000)

        const startUtc = newStart.toISOString()
        const endUtc = newEnd.toISOString()

        if (d.block.entry_type === "event") {
          const eventId = d.block.id.replace("event-", "")
          api.updateCalendarEvent(eventId, {
            title: d.block.task_title,
            start_time: startUtc,
            end_time: endUtc,
          }).then(() => refresh())
        } else {
          // Task block — patch task and rebuild schedule
          api.updateTask(d.block.id, { scheduled_time: startUtc }).then(() => rebuildAndRefresh())
        }
        return null
      })
    }

    window.addEventListener("mousemove", onMouseMove)
    window.addEventListener("mouseup", onMouseUp)
  }

  async function handleRebuild() {
    setRebuilding(true)
    await rebuildAndRefresh()
    setRebuilding(false)
  }

  return (
    <>
      <div className="flex-1 flex flex-col min-h-0 px-4 md:px-6 py-6 pb-24 md:pb-6 gap-4">
        {/* Toolbar */}
        <div className="flex items-center justify-between gap-4 flex-wrap shrink-0">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setAnchor(startOfDay(new Date()))}
              className="text-xs px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-lg transition text-gray-600 font-medium"
            >
              Today
            </button>
            <button onClick={() => nav(-1)} className="text-gray-400 hover:text-gray-700 px-2 text-lg leading-none">‹</button>
            <button onClick={() => nav(1)} className="text-gray-400 hover:text-gray-700 px-2 text-lg leading-none">›</button>
            <span className="text-sm font-semibold text-gray-900">{headerLabel}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCreateSlot({ day: anchor, minsFromStart: 9 * 60 - HOUR_START * 60 })}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium transition"
            >
              <Plus className="h-3.5 w-3.5" />
              Add event
            </button>
            <button
              onClick={handleRebuild}
              disabled={rebuilding}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-600 font-medium transition disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${rebuilding ? "animate-spin" : ""}`} />
              Sync schedule
            </button>
            <div className="flex gap-1 bg-gray-100 rounded-xl p-1 text-xs">
              {(["day", "week", "month"] as View[]).map((v) => (
                <button
                  key={v}
                  onClick={() => { setView(v); localStorage.setItem("calendar_view", v) }}
                  className={`px-3 py-1.5 rounded-lg capitalize transition font-medium ${
                    view === v ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Calendar grid */}
        <div ref={gridRef} className="flex-1 min-h-0 bg-white border border-gray-200 rounded-2xl overflow-hidden">
          {loading ? (
            <div className="h-full flex items-center justify-center text-sm text-gray-400">Loading…</div>
          ) : view === "month" ? (
            <MonthGrid
              anchor={anchor}
              blocks={visibleBlocks}
              onDayClick={(day) => { setAnchor(day); setView("day"); localStorage.setItem("calendar_view", "day") }}
              onBlockClick={(block, x, y) => setSelectedBlock({ block, x, y })}
              onCreateClick={(day) => setCreateSlot({ day, minsFromStart: 9 * 60 - HOUR_START * 60 })}
            />
          ) : (
            <TimeGrid
              days={days}
              blocks={visibleBlocks}
              onClickSlot={handleClickSlot}
              onDragStart={handleDragStart}
            />
          )}
        </div>
      </div>

      {/* Create event popover */}
      {createSlot && (
        <CreatePopover
          initialDay={createSlot.day}
          initialMinsFromStart={createSlot.minsFromStart}
          onSave={handleCreateEvent}
          onClose={() => setCreateSlot(null)}
        />
      )}

      {/* Block edit / detail popover */}
      {selectedBlock && (
        <BlockEditModal
          block={selectedBlock.block}
          anchorX={selectedBlock.x}
          anchorY={selectedBlock.y}
          onClose={() => setSelectedBlock(null)}
          onSaveEvent={handleSaveEvent}
          onDeleteEvent={handleDeleteEvent}
          onCompleteTask={handleCompleteTask}
        />
      )}
    </>
  )
}
