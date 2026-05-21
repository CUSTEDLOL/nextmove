/** Round `minutes` down to the nearest `intervalMins` boundary. */
export function snapToInterval(minutes: number, intervalMins: number): number {
  return Math.floor(minutes / intervalMins) * intervalMins
}

/**
 * Convert a `datetime-local` input value ("2026-04-09T21:00") to a UTC ISO
 * string ("2026-04-09T13:00:00.000Z" for UTC+8).
 * The browser interprets the bare string as local time, so `new Date()` gives
 * the correct UTC epoch and `.toISOString()` serialises it.
 */
export function localInputToUtc(localDatetimeStr: string): string {
  return new Date(localDatetimeStr).toISOString()
}

/**
 * Convert a UTC ISO string (or naive string from the backend) to a local Date.
 * Backend sends naive UTC datetimes — append "Z" so the browser treats them as UTC
 * and auto-converts to local time.
 */
export function parseLocal(s: string): Date {
  const isUtcOrOffset = s.includes("Z") || /[+-]\d{2}:\d{2}$/.test(s)
  const normalized = isUtcOrOffset ? s.replace(" ", "T") : s.replace(" ", "T") + "Z"
  return new Date(normalized)
}

/**
 * Minutes elapsed since `hourStart` for a given Date (in local time).
 * e.g. date=09:30, hourStart=7 → 150
 */
export function minsFromHourStart(date: Date, hourStart: number): number {
  return (date.getHours() - hourStart) * 60 + date.getMinutes()
}

/** Convert minutes to pixels given `hourPx` pixels per hour. */
export function pxFromMins(mins: number, hourPx: number): number {
  return (mins / 60) * hourPx
}

/** Convert pixels to minutes given `hourPx` pixels per hour. */
export function minsFromPx(px: number, hourPx: number): number {
  return (px / hourPx) * 60
}

/** Format a Date as "9:00 AM". */
export function fmtTime(d: Date): string {
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true })
}

/** Format a Date as "Apr 7". */
export function fmtMonthDay(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

/** Format an hour number as "9am" / "2pm". */
export function fmtHour(h: number): string {
  const ap = h < 12 ? "am" : "pm"
  const h12 = h % 12 === 0 ? 12 : h % 12
  return `${h12}${ap}`
}

/** "YYYY-MM-DD" key for grouping blocks by day. */
export function dayKey(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function startOfDay(d: Date): Date {
  const x = new Date(d)
  x.setHours(0, 0, 0, 0)
  return x
}

export function addDays(d: Date, n: number): Date {
  const x = new Date(d)
  x.setDate(x.getDate() + n)
  return x
}

export function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
}

/** Convert a local Date to a "datetime-local" input value ("2026-04-09T09:00"). */
export function toLocalInputValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
