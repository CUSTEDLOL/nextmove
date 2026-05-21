export type DashboardTaskLike = {
  id: string
  title: string
  is_primary: boolean
  state: string
}

export function deriveDashboardTasks<T extends DashboardTaskLike>(tasks: T[]) {
  const activeTasks = tasks.filter((task) => task.state !== "completed")
  const primaryTask =
    activeTasks.find((task) => task.is_primary) ??
    activeTasks[0] ??
    null

  const secondaryTasks = activeTasks
    .filter((task) => task.id !== primaryTask?.id)
    .slice(0, 3)

  return {
    primaryTask,
    secondaryTasks,
    isQueueEmpty: activeTasks.length === 0,
  }
}
