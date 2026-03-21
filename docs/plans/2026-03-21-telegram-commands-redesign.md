# Telegram Bot — Commands Redesign

**Date:** 2026-03-21
**Status:** Approved

---

## Problem

The current conversational-only bot is hard to use. Users don't know what to type, can't navigate back to the menu, can't edit tasks, and the task list has no actionable buttons.

---

## Decision

Switch to **Option C: commands + brain dump as the only free text.**

Mental model:
- Slash commands for all navigation and actions
- Free text = add tasks (brain dump), always — except when in edit mode
- Edit mode is explicit: user selects a task first, then types what to change

---

## Command Set

| Command | Description |
|---|---|
| `/menu` | Show main menu with inline buttons |
| `/today` | Today's #1 task + 2–3 secondary, with Done / Skip / Steps / Why buttons |
| `/list` | All pending tasks, each with ✅ Done and ⏭️ Skip inline buttons |
| `/dump` | Prompt to brain dump; next free-text message adds tasks |
| `/done` | Mark top task complete immediately |
| `/skip` | Skip (reschedule) top task immediately |
| `/edit` | Show task list → tap a task → type what to change |
| `/web` | Reply with a button linking to the web app |

---

## Edit Flow

1. `/edit` → bot shows all pending tasks as inline keyboard (one button per task, truncated to 30 chars)
2. User taps a task → bot stores `pending_edit_task_id` on the User row and replies:
   > "What do you want to change?\n_(e.g. 'deadline is Friday', 'rename to Study for exam', 'delete')_"
3. User types instruction in natural language
4. GPT-4o parses the instruction into a structured edit: `{field: "deadline"|"title"|"delete", value: ...}`
5. Bot applies the edit, clears `pending_edit_task_id`, confirms:
   > "✅ Updated: deadline → Friday 28 Mar"

**Cancellation:** If user types `/menu`, `/list`, or any other command while in edit mode, the edit is cancelled silently and the command runs normally.

---

## Free Text Behaviour

| State | What free text does |
|---|---|
| Normal | Brain dump — parsed as tasks and added |
| `pending_edit_task_id` set | Parsed as edit instruction for that task |
| `pending_steps_task_id` set | Parsed as steps for that task (existing behaviour) |

Priority: `pending_steps_task_id` > `pending_edit_task_id` > brain dump.

---

## Data Model Changes

Add `pending_edit_task_id UUID REFERENCES tasks(id)` column to `users` table (nullable).

---

## Bot Registration

All 8 commands registered with `setMyCommands` so they appear in Telegram's command menu (the `/` autocomplete popup).

---

## Web Link

`/web` replies with an inline keyboard button: `🌐 Open NextMove` → `https://<NEXTMOVE_WEB_URL>`. URL read from `settings.web_url` (env var `WEB_URL`, defaults to `http://localhost:3000`).

---

## Out of Scope

- Editing effort or importance via Telegram (web app only for now)
- Multi-step edit wizard
- Undo after edit
