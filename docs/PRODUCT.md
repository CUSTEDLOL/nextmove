# NextMove — Product Specification

## Vision

Students are overwhelmed not because they have too much to do, but because they spend too much mental energy deciding what to do next. NextMove eliminates that decision. It knows your deadlines, your calendar, your energy — and tells you exactly what to work on right now.

---

## Target User

**Primary:** University/college student
- Has 5–15 active tasks across multiple subjects at any time
- Procrastinates due to overwhelm, not laziness
- Lives on their phone and uses Telegram
- Has a Google account and calendar (but may not maintain it well)
- Is resistant to complex productivity systems

---

## Core Interaction Principle

> The user sees **ONE primary task** + 2–3 secondary tasks.
> All planning complexity is hidden.

The system handles: prioritization, scheduling, rescheduling, deadline tracking, procrastination nudges.
The user handles: doing the work.

---

## User Flows

### Onboarding
```
1. Sign up (Google OAuth or email/password)
2. Connect Google Calendar (optional — can use built-in calendar)
3. Set timezone + rough daily schedule (when do you usually study?)
4. Brain dump: "Tell me everything on your plate right now"
5. AI parses → matrix scores → schedule built
6. User sees: "Your #1 task today is: [Task]"
```

### Daily Flow
```
Morning (8am):
  Telegram / web notification → "Good morning! Today's focus: [Task]"
  Shows: primary task + 2-3 secondary tasks + today's schedule

Daytime:
  User marks task started → timer begins (optional)
  Pre-task nudge 15 min before scheduled slot
  Task completed → logged → next task surfaced

Missed task:
  Auto-detected after scheduled slot passes
  Rescheduled to next available slot
  Evening notification: "You missed [Task]. Moved to [new time]."
```

### Brain Dump Flow
```
User (Telegram or web): "I need to finish the stats assignment by Thursday,
study for econ midterm next Tuesday, and read chapter 5 tonight."

AI parses → extracts 3 tasks with deadlines/effort
Matrix scores each → Priority Index calculated
Scheduler places them in free calendar slots
User sees: updated task list + "Your #1 task is now: [Task]"
```

### Procrastination Flow
```
Task scheduled for 2pm → no activity logged by 2:30pm
Telegram message: "Hey, you were supposed to start [Task]. What's up?"
Options shown: [I'm on it] [I'm stuck] [I need to reschedule]
  → "I'm stuck": "What's blocking you? [free text]" → AI suggests next step
  → "Reschedule": shows next 3 available slots to pick from
  → "I'm on it": logs start time
```

### Weekly Intelligence Flow (Phase 2)
```
Sunday 7pm:
  "Here's your week in review:"
  - X tasks completed, Y missed
  - Your most productive days: Tue, Thu
  - Best focus window: 9am–12pm
  Next week's tasks are already scheduled. Want to review?
```

---

## Feature Phases

### Phase 1 — MVP
- [x] Google OAuth + email/password auth
- [x] Brain dump → AI parse → matrix score → schedule
- [x] Built-in calendar (Cal.com style) + Google Calendar integration
- [x] Today's task view (web + Telegram)
- [x] Task management (add, complete, reschedule)
- [x] Morning brief + procrastination interrupt (Telegram)
- [x] Web dashboard: today view, upcoming schedule, task list

### Phase 2 — Intelligence
- [ ] Gmail scanning for commitments
- [ ] Behavior learning (productivity peaks, actual durations)
- [ ] Weekly insights report
- [ ] Energy window optimization

### Phase 3 — Polish
- [ ] Hybrid effort inference (AI-assisted)
- [ ] Mobile app (React Native)
- [ ] Advanced nudge personalization
- [ ] Team/study group mode

---

## Telegram Bot Commands

```
/start          — onboarding
/today          — show today's task + schedule
/dump           — start a brain dump (free text follows)
/tasks          — list all active tasks
/done [task]    — mark task complete
/skip [task]    — reschedule task
/add [task]     — add single task
/schedule       — show this week's schedule
/help           — show commands
```

Every action also has a button-based flow (InlineKeyboard) for non-command users.

---

## Web App Pages

```
/                   → Landing / marketing
/login              → Auth (Google + email)
/dashboard          → Today's task + 2-3 secondary + calendar strip
/tasks              → Full task list with filters
/schedule           → Weekly calendar view (built-in or Google)
/settings           → Profile, calendar connection, notification preferences
/onboarding         → First-run brain dump + setup
```
