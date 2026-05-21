import { getSession, signOut } from "next-auth/react"

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
let signOutInFlight = false

export class ApiError extends Error {
  code: "auth_required" | "unauthorized" | "network" | "http"
  status?: number

  constructor(
    code: "auth_required" | "unauthorized" | "network" | "http",
    message: string,
    status?: number
  ) {
    super(message)
    this.code = code
    this.status = status
  }
}

function isAuthErrorStatus(status: number) {
  return status === 401 || status === 403
}

async function forceLogin() {
  if (signOutInFlight) return
  signOutInFlight = true
  try {
    await signOut({ callbackUrl: "/login" })
  } finally {
    signOutInFlight = false
  }
}

async function authFetch(path: string, options: RequestInit = {}) {
  const session = await getSession()
  const token = (session as { accessToken?: string } | null)?.accessToken
  if (!token) {
    void forceLogin()
    throw new ApiError("auth_required", "Your session expired. Please sign in again.")
  }

  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(options.headers || {}),
      },
    })
  } catch {
    throw new ApiError("network", "Could not reach the backend API.")
  }

  if (isAuthErrorStatus(res.status)) {
    void forceLogin()
    throw new ApiError("unauthorized", "Your session expired. Please sign in again.", res.status)
  }

  if (!res.ok) throw new ApiError("http", `API error ${res.status}`, res.status)
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  getTodayTasks: () => authFetch("/api/tasks/today"),
  listTasks: () => authFetch("/api/tasks"),
  getTask: (id: string) => authFetch(`/api/tasks/${id}`),
  addTask: (data: object) => authFetch("/api/tasks", { method: "POST", body: JSON.stringify(data) }),
  updateTask: (id: string, data: object) => authFetch(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteTask: (id: string) => authFetch(`/api/tasks/${id}`, { method: "DELETE" }),
  brainDump: (text: string) => authFetch("/api/tasks/dump", { method: "POST", body: JSON.stringify({ text }) }),
  completeTask: (id: string) => authFetch(`/api/tasks/${id}/complete`, { method: "POST" }),
  rescheduleTask: (id: string) => authFetch(`/api/tasks/${id}/reschedule`, { method: "POST" }),
  whyTask: (id: string) => authFetch(`/api/tasks/${id}/why`),
  getSteps: (id: string) => authFetch(`/api/tasks/${id}/steps`),
  addSteps: (id: string, text: string) => authFetch(`/api/tasks/${id}/steps`, { method: "POST", body: JSON.stringify({ text }) }),
  getScheduleBlocks: () => authFetch("/api/schedule"),
  rebuildSchedule: () => authFetch("/api/schedule/rebuild", { method: "POST" }),
  getScheduleFreeSlots: () => authFetch("/api/schedule/free-slots"),
  getCalendarEvents: () => authFetch("/api/calendar/events"),
  createCalendarEvent: (data: object) => authFetch("/api/calendar/events", { method: "POST", body: JSON.stringify(data) }),
  updateCalendarEvent: (id: string, data: object) => authFetch(`/api/calendar/events/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteCalendarEvent: (id: string) => authFetch(`/api/calendar/events/${id}`, { method: "DELETE" }),
  getCalendarStatus: () => authFetch("/api/calendar/status"),
  connectCalendar: () => authFetch("/api/calendar/connect", { method: "POST" }),
  disconnectCalendar: () => authFetch("/api/calendar/disconnect", { method: "POST" }),
  getMe: () => authFetch("/api/users/me"),
  updateMe: (data: object) => authFetch("/api/users/me", { method: "PATCH", body: JSON.stringify(data) }),
  getTelegramLinkToken: () => authFetch("/api/telegram/link-token", { method: "POST" }),
  getTelegramLinkStatus: () => authFetch("/api/telegram/link-status") as Promise<{ linked: boolean }>,
}
