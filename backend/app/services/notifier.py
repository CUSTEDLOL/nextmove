from typing import Optional
from app.schemas.tasks import TaskResponse
from app.telegram.utils import esc


def build_morning_brief(
    name: str,
    primary: Optional[TaskResponse],
    secondary: list[TaskResponse]
) -> str:
    greeting = f"Good morning, {esc(name)}\\! ☀️\n\n"
    if not primary:
        return greeting + "You have no pending tasks today — enjoy the clear schedule\\! 🎉\nAdd tasks anytime with /dump\\."

    lines = [greeting, f"🎯 *Today's focus:*\n*{esc(primary.title)}*"]
    if primary.effort:
        lines.append(f"   ⚡ Effort: {esc(primary.effort.capitalize())}")
    if primary.deadline:
        lines.append(f"   📅 Due: {esc(primary.deadline.strftime('%a %b %d'))}")
    if secondary:
        lines.append("\n📋 *Also scheduled:*")
        for t in secondary:
            lines.append(f"   • {esc(t.title)}")
    lines.append("\nYou've got this\\! Use /done when finished\\. 💪")
    return "\n".join(lines)


def build_procrastination_prompt(task: TaskResponse) -> str:
    return (
        f"👀 Hey — you were supposed to start *{esc(task.title)}* a while ago\\.\n\n"
        f"What's going on\\?\n\n"
        f"\\[✅ I'm on it\\]  \\[🤔 I'm stuck\\]  \\[📅 Reschedule\\]"
    )


def build_pretask_nudge(task: TaskResponse) -> str:
    return (
        f"⏰ *Starting in 15 minutes:*\n{esc(task.title)}\n\n"
        f"Clear your space, silence your phone, and get ready\\. You've got this\\."
    )


def build_evening_wrapup(completed_count: int, missed_count: int) -> str:
    if completed_count == 0 and missed_count == 0:
        return "🌙 *Evening check\\-in:* No tasks were scheduled today\\. Start fresh tomorrow\\!"

    lines = ["🌙 *Day wrap\\-up:*"]
    if completed_count:
        lines.append(f"   ✅ Completed: {completed_count} task{'s' if completed_count > 1 else ''}")
    if missed_count:
        lines.append(f"   ⏭️ Rescheduled: {missed_count} task{'s' if missed_count > 1 else ''}")
    lines.append("\nSee you tomorrow\\! 🌟")
    return "\n".join(lines)


def build_weekly_summary(
    name: str,
    completed: int,
    missed: int,
    best_days: list[str]
) -> str:
    lines = [f"📊 *Weekly summary for {esc(name)}:*\n"]
    lines.append(f"✅ Completed: {completed} tasks")
    lines.append(f"⏭️ Missed: {missed} tasks")
    if best_days:
        lines.append(f"🏆 Most productive: {esc(', '.join(best_days))}")
    lines.append("\nNext week's schedule is ready\\. Use /today to see what's first\\.")
    return "\n".join(lines)
