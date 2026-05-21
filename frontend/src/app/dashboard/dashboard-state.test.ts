import test from "node:test"
import assert from "node:assert/strict"

import { deriveDashboardTasks } from "./dashboard-state.ts"

test("promotes the next active task to primary after refresh", () => {
  const result = deriveDashboardTasks([
    { id: "task-2", title: "Prepare outline", is_primary: true, state: "scheduled" },
    { id: "task-3", title: "Review notes", is_primary: false, state: "pending" },
    { id: "task-4", title: "Reply to advisor", is_primary: false, state: "pending" },
  ])

  assert.equal(result.primaryTask?.id, "task-2")
  assert.deepEqual(
    result.secondaryTasks.map((task) => task.id),
    ["task-3", "task-4"]
  )
  assert.equal(result.isQueueEmpty, false)
})

test("falls back to the first active task when no item is explicitly marked primary", () => {
  const result = deriveDashboardTasks([
    { id: "task-3", title: "Review notes", is_primary: false, state: "pending" },
    { id: "task-4", title: "Reply to advisor", is_primary: false, state: "scheduled" },
  ])

  assert.equal(result.primaryTask?.id, "task-3")
  assert.deepEqual(result.secondaryTasks.map((task) => task.id), ["task-4"])
})

test("caps secondary tasks at three items", () => {
  const result = deriveDashboardTasks([
    { id: "task-1", title: "Task 1", is_primary: true, state: "pending" },
    { id: "task-2", title: "Task 2", is_primary: false, state: "pending" },
    { id: "task-3", title: "Task 3", is_primary: false, state: "pending" },
    { id: "task-4", title: "Task 4", is_primary: false, state: "pending" },
    { id: "task-5", title: "Task 5", is_primary: false, state: "pending" },
  ])

  assert.deepEqual(
    result.secondaryTasks.map((task) => task.id),
    ["task-2", "task-3", "task-4"]
  )
})

test("reports an empty queue when there are no active tasks", () => {
  const result = deriveDashboardTasks([
    { id: "task-1", title: "Done", is_primary: true, state: "completed" },
  ])

  assert.equal(result.primaryTask, null)
  assert.deepEqual(result.secondaryTasks, [])
  assert.equal(result.isQueueEmpty, true)
})
