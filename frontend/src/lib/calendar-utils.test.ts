import test from "node:test"
import assert from "node:assert/strict"
import {
  snapToInterval,
  localInputToUtc,
  minsFromHourStart,
  pxFromMins,
  minsFromPx,
  parseLocal,
  dayKey,
} from "./calendar-utils.ts"

test("snapToInterval rounds down to nearest 15 min", () => {
  assert.equal(snapToInterval(7, 15), 0)
  assert.equal(snapToInterval(15, 15), 15)
  assert.equal(snapToInterval(22, 15), 15)
  assert.equal(snapToInterval(45, 15), 45)
  assert.equal(snapToInterval(59, 15), 45)
})

test("snapToInterval works for 30-min intervals", () => {
  assert.equal(snapToInterval(0, 30), 0)
  assert.equal(snapToInterval(29, 30), 0)
  assert.equal(snapToInterval(30, 30), 30)
})

test("localInputToUtc converts datetime-local string to ISO UTC", () => {
  // We can only test the format, not the exact offset (depends on TZ env)
  const result = localInputToUtc("2026-04-09T09:00")
  assert.ok(result.endsWith("Z"), `expected Z suffix, got ${result}`)
  assert.ok(result.includes("T"), "expected ISO T separator")
})

test("minsFromHourStart computes offset from grid start", () => {
  // Use Date constructor with explicit parts (always local time, no TZ ambiguity)
  const d = new Date(2026, 3, 9, 9, 30) // month is 0-indexed: 3 = April
  assert.equal(minsFromHourStart(d, 7), 150)
})

test("pxFromMins and minsFromPx are inverse at HOUR_PX=60", () => {
  assert.equal(pxFromMins(60, 60), 60)
  assert.equal(pxFromMins(30, 60), 30)
  assert.equal(minsFromPx(60, 60), 60)
  assert.equal(minsFromPx(30, 60), 30)
})

test("parseLocal handles naive UTC string from backend", () => {
  const d = parseLocal("2026-04-09 09:00:00")
  // Should be treated as UTC → 09:00 UTC
  assert.equal(d.toISOString(), "2026-04-09T09:00:00.000Z")
})

test("parseLocal leaves already-UTC strings unchanged", () => {
  const d = parseLocal("2026-04-09T09:00:00Z")
  assert.equal(d.toISOString(), "2026-04-09T09:00:00.000Z")
})

test("dayKey produces zero-padded YYYY-MM-DD key", () => {
  const d = new Date(2026, 0, 9)  // Jan 9 (month 0)
  assert.equal(dayKey(d), "2026-01-09")
})
