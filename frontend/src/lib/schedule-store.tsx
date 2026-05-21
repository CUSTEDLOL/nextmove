"use client"

import { createContext, useCallback, useContext, useEffect, useState } from "react"
import { api } from "@/lib/api"

// Module-level cache — survives component remounts within the same browser session.
// Prevents re-fetching schedule data on every page navigation.
let _cache: Block[] = []
let _lastFetchMs = 0
const STALE_MS = 60_000 // 60 seconds

export interface Block {
  id: string
  task_title: string
  effort: string | null
  start_time: string
  end_time: string
  entry_type: "block" | "deadline" | "prep" | "event"
}

interface ScheduleContextType {
  blocks: Block[]
  loading: boolean
  /** Re-fetch schedule blocks + calendar events without a rebuild. */
  refresh: () => Promise<void>
  /** Re-fetch unconditionally, ignoring the stale cache. */
  forceRefresh: () => Promise<void>
  /** Trigger a full schedule rebuild, then re-fetch. */
  rebuildAndRefresh: () => Promise<void>
}

const ScheduleContext = createContext<ScheduleContextType>({
  blocks: [],
  loading: true,
  refresh: async () => {},
  forceRefresh: async () => {},
  rebuildAndRefresh: async () => {},
})

export function ScheduleProvider({ children }: { children: React.ReactNode }) {
  const [blocks, setBlocks] = useState<Block[]>(() => _cache)
  const [loading, setLoading] = useState(() => _cache.length === 0)

  const refresh = useCallback(async () => {
    if (Date.now() - _lastFetchMs < STALE_MS) return  // data is fresh, skip
    try {
      const [scheduleBlocks, events] = await Promise.all([
        api.getScheduleBlocks(),
        api.getCalendarEvents(),
      ])
      const eventBlocks = (events as Array<Record<string, unknown>>).map((e) => ({
        id: `event-${String(e.id)}`,
        task_title: String(e.title),
        effort: null,
        start_time: String(e.start_time),
        end_time: String(e.end_time),
        entry_type: "event" as const,
      }))
      const merged = [...(scheduleBlocks as Block[]), ...eventBlocks]
      _cache = merged
      _lastFetchMs = Date.now()
      setBlocks(merged)
    } catch {
      // Keep stale data on network error.
    } finally {
      setLoading(false)
    }
  }, [])

  const forceRefresh = useCallback(async () => {
    _lastFetchMs = 0
    await refresh()
  }, [refresh])

  const rebuildAndRefresh = useCallback(async () => {
    try {
      await api.rebuildSchedule()
    } catch {
      // Even if rebuild fails, still refresh to show current state.
    }
    _lastFetchMs = 0  // invalidate cache so refresh always re-fetches after a rebuild
    await refresh()
  }, [refresh])

  useEffect(() => {
    refresh()
  }, [refresh])

  return (
    <ScheduleContext.Provider value={{ blocks, loading, refresh, forceRefresh, rebuildAndRefresh }}>
      {children}
    </ScheduleContext.Provider>
  )
}

export function useSchedule() {
  return useContext(ScheduleContext)
}
