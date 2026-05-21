# NextMove Frontend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the complete NextMove web frontend in Next.js 16 with a clean light-mode UI, emerald accent, left sidebar navigation, hero task card, brain dump input, task edit drawer, and fullscreen onboarding tour.

**Architecture:** Next.js 16 App Router with TypeScript and Tailwind CSS v4. shadcn/ui provides base components (Button, Input, Sheet, Badge, Dialog). All pages use a shared AppLayout wrapper that renders the left sidebar on desktop and bottom tab bar on mobile. State is local (useState/useContext) in MVP — no global state library needed yet.

**Tech Stack:** Next.js 16, TypeScript, Tailwind CSS v4, shadcn/ui, next-auth v4, axios, lucide-react (icons)

---

## Design Tokens (reference throughout)

```
Accent:       emerald-500  (#10B981)
Accent hover: emerald-600  (#059669)
Background:   white
Surface:      gray-50
Border:       gray-200
Text primary: gray-900
Text muted:   gray-500
Sidebar width: 240px (desktop)
```

---

### Task 1: Install shadcn/ui and lucide-react

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/app/globals.css`
- Create: `frontend/components.json`

**Step 1: Install dependencies**

```bash
cd frontend
npx shadcn@latest init --yes
npm install lucide-react clsx tailwind-merge class-variance-authority
```

When prompted by shadcn init:
- Style: Default
- Base color: Neutral
- CSS variables: Yes

**Step 2: Add shadcn components needed**

```bash
npx shadcn@latest add button input badge sheet dialog separator scroll-area
```

**Step 3: Verify install**

Run: `npm run build`
Expected: Compiles with no errors.

**Step 4: Commit**

```bash
git add frontend/package.json frontend/components.json frontend/src/app/globals.css frontend/src/lib/utils.ts frontend/src/components/ui/
git commit -m "feat: install shadcn/ui and lucide-react"
```

---

### Task 2: Global CSS and design tokens

**Files:**
- Modify: `frontend/src/app/globals.css`

**Step 1: Replace globals.css with NextMove tokens**

```css
@import "tailwindcss";

:root {
  --background: #ffffff;
  --foreground: #111827;
  --surface: #f9fafb;
  --border: #e5e7eb;
  --muted: #6b7280;
  --accent: #10b981;
  --accent-hover: #059669;
  --accent-light: #d1fae5;
  --sidebar-width: 240px;
  --radius: 0.5rem;
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --font-sans: var(--font-geist-sans);
}

* {
  box-sizing: border-box;
}

body {
  background: var(--background);
  color: var(--foreground);
  font-family: var(--font-sans), system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
```

**Step 2: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "feat: add NextMove design tokens to globals.css"
```

---

### Task 3: Shared types

**Files:**
- Create: `frontend/src/types/index.ts`

**Step 1: Create types file**

```typescript
// frontend/src/types/index.ts

export type TaskState =
  | "pending"
  | "scheduled"
  | "in_progress"
  | "completed"
  | "missed"
  | "rescheduled";

export interface Task {
  id: string;
  title: string;
  effort: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10;
  deadline: string | null; // ISO date string
  state: TaskState;
  priority_score: number; // 0–10
  is_primary: boolean;
  notes: string | null;
  created_at: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  avatar_url: string | null;
}

export type NavItem = {
  label: string;
  href: string;
  icon: string; // lucide icon name
};
```

**Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add shared TypeScript types"
```

---

### Task 4: Mock data for development

**Files:**
- Create: `frontend/src/lib/mock-data.ts`

**Step 1: Create mock tasks**

```typescript
// frontend/src/lib/mock-data.ts
import { Task } from "@/types";

export const MOCK_TASKS: Task[] = [
  {
    id: "1",
    title: "Write literature review for CS thesis",
    effort: 8,
    deadline: new Date(Date.now() + 86400000).toISOString(), // tomorrow
    state: "in_progress",
    priority_score: 9.2,
    is_primary: true,
    notes: "Focus on sections 2.1 and 2.3 first",
    created_at: new Date().toISOString(),
  },
  {
    id: "2",
    title: "Submit ECON 301 problem set",
    effort: 5,
    deadline: new Date(Date.now() + 172800000).toISOString(), // 2 days
    state: "pending",
    priority_score: 7.8,
    is_primary: false,
    notes: null,
    created_at: new Date().toISOString(),
  },
  {
    id: "3",
    title: "Email professor about office hours",
    effort: 2,
    deadline: null,
    state: "pending",
    priority_score: 5.1,
    is_primary: false,
    notes: null,
    created_at: new Date().toISOString(),
  },
  {
    id: "4",
    title: "Review lecture notes for midterm",
    effort: 6,
    deadline: new Date(Date.now() + 432000000).toISOString(), // 5 days
    state: "pending",
    priority_score: 6.4,
    is_primary: false,
    notes: null,
    created_at: new Date().toISOString(),
  },
];
```

**Step 2: Commit**

```bash
git add frontend/src/lib/mock-data.ts
git commit -m "feat: add mock task data for dev"
```

---

### Task 5: AppLayout — sidebar + bottom tab bar

**Files:**
- Create: `frontend/src/components/layout/Sidebar.tsx`
- Create: `frontend/src/components/layout/BottomTabBar.tsx`
- Create: `frontend/src/components/layout/AppLayout.tsx`

**Step 1: Create Sidebar component**

```tsx
// frontend/src/components/layout/Sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, CheckSquare, Calendar, Settings, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Tasks", href: "/tasks", icon: CheckSquare },
  { label: "Calendar", href: "/calendar", icon: Calendar },
  { label: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden md:flex flex-col w-[240px] min-h-screen border-r border-[var(--border)] bg-white px-4 py-6">
      {/* Logo */}
      <div className="flex items-center gap-2 mb-8 px-2">
        <div className="w-7 h-7 rounded-lg bg-emerald-500 flex items-center justify-center">
          <Zap className="w-4 h-4 text-white" fill="white" />
        </div>
        <span className="font-semibold text-gray-900 text-base tracking-tight">NextMove</span>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1 flex-1">
        {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                active
                  ? "bg-emerald-50 text-emerald-700"
                  : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
              )}
            >
              <Icon className={cn("w-4 h-4", active ? "text-emerald-600" : "text-gray-400")} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* User avatar placeholder */}
      <div className="flex items-center gap-3 px-2 pt-4 border-t border-[var(--border)]">
        <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-xs font-medium text-gray-600">
          VJ
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">Vishesh</p>
          <p className="text-xs text-gray-500 truncate">student</p>
        </div>
      </div>
    </aside>
  );
}
```

**Step 2: Create BottomTabBar component**

```tsx
// frontend/src/components/layout/BottomTabBar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, CheckSquare, Calendar, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const TABS = [
  { label: "Home", href: "/dashboard", icon: LayoutDashboard },
  { label: "Tasks", href: "/tasks", icon: CheckSquare },
  { label: "Calendar", href: "/calendar", icon: Calendar },
  { label: "Settings", href: "/settings", icon: Settings },
];

export function BottomTabBar() {
  const pathname = usePathname();

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-[var(--border)] px-2 pb-safe">
      <div className="flex items-center justify-around h-16">
        {TABS.map(({ label, href, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className="flex flex-col items-center gap-1 px-4 py-2"
            >
              <Icon
                className={cn(
                  "w-5 h-5",
                  active ? "text-emerald-600" : "text-gray-400"
                )}
              />
              <span
                className={cn(
                  "text-[10px] font-medium",
                  active ? "text-emerald-600" : "text-gray-400"
                )}
              >
                {label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
```

**Step 3: Create AppLayout component**

```tsx
// frontend/src/components/layout/AppLayout.tsx
import { Sidebar } from "./Sidebar";
import { BottomTabBar } from "./BottomTabBar";

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-[var(--background)]">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0">
        {children}
      </main>
      <BottomTabBar />
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add frontend/src/components/layout/
git commit -m "feat: add AppLayout with sidebar and bottom tab bar"
```

---

### Task 6: BrainDumpBar component

**Files:**
- Create: `frontend/src/components/dashboard/BrainDumpBar.tsx`

**Step 1: Create BrainDumpBar**

```tsx
// frontend/src/components/dashboard/BrainDumpBar.tsx
"use client";

import { useState } from "react";
import { Send, Sparkles } from "lucide-react";

interface BrainDumpBarProps {
  onSubmit?: (text: string) => void;
}

export function BrainDumpBar({ onSubmit }: BrainDumpBarProps) {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!value.trim()) return;
    setLoading(true);
    await onSubmit?.(value.trim());
    setValue("");
    setLoading(false);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-center gap-3 bg-white border border-[var(--border)] rounded-xl px-4 py-3 shadow-sm"
    >
      <Sparkles className="w-4 h-4 text-emerald-500 shrink-0" />
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Brain dump anything — tasks, deadlines, commitments..."
        className="flex-1 text-sm text-gray-900 placeholder:text-gray-400 bg-transparent outline-none"
        disabled={loading}
      />
      <button
        type="submit"
        disabled={!value.trim() || loading}
        className="w-8 h-8 rounded-lg bg-emerald-500 hover:bg-emerald-600 disabled:bg-gray-100 disabled:cursor-not-allowed flex items-center justify-center transition-colors shrink-0"
      >
        <Send className="w-3.5 h-3.5 text-white disabled:text-gray-400" />
      </button>
    </form>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/dashboard/BrainDumpBar.tsx
git commit -m "feat: add BrainDumpBar component"
```

---

### Task 7: HeroTaskCard component

**Files:**
- Create: `frontend/src/components/dashboard/HeroTaskCard.tsx`

**Step 1: Create HeroTaskCard**

```tsx
// frontend/src/components/dashboard/HeroTaskCard.tsx
"use client";

import { Check, Clock, Flame, ChevronRight } from "lucide-react";
import { Task } from "@/types";
import { cn } from "@/lib/utils";

interface HeroTaskCardProps {
  task: Task;
  onComplete: (id: string) => void;
  onEdit: (task: Task) => void;
}

function effortLabel(effort: number): string {
  if (effort <= 3) return "Light";
  if (effort <= 6) return "Medium";
  return "Heavy";
}

function effortColor(effort: number): string {
  if (effort <= 3) return "bg-blue-50 text-blue-700";
  if (effort <= 6) return "bg-amber-50 text-amber-700";
  return "bg-rose-50 text-rose-700";
}

function formatDeadline(iso: string | null): string {
  if (!iso) return "No deadline";
  const d = new Date(iso);
  const today = new Date();
  const diff = Math.ceil((d.getTime() - today.getTime()) / 86400000);
  if (diff === 0) return "Due today";
  if (diff === 1) return "Due tomorrow";
  if (diff < 0) return `${Math.abs(diff)}d overdue`;
  return `Due in ${diff}d`;
}

export function HeroTaskCard({ task, onComplete, onEdit }: HeroTaskCardProps) {
  return (
    <div className="w-full bg-white border border-[var(--border)] rounded-2xl p-6 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-semibold text-emerald-600 uppercase tracking-wider">
          Today's #1 Task
        </span>
        <span className="text-xs font-medium text-gray-400">
          Score {task.priority_score.toFixed(1)}
        </span>
      </div>

      {/* Title */}
      <h2 className="text-xl font-semibold text-gray-900 leading-snug mb-4">
        {task.title}
      </h2>

      {/* Meta */}
      <div className="flex items-center gap-3 mb-6">
        <span className={cn("text-xs font-medium px-2.5 py-1 rounded-full", effortColor(task.effort))}>
          <Flame className="w-3 h-3 inline mr-1 -mt-0.5" />
          {effortLabel(task.effort)} effort
        </span>
        <span className="flex items-center gap-1 text-xs text-gray-500">
          <Clock className="w-3.5 h-3.5" />
          {formatDeadline(task.deadline)}
        </span>
      </div>

      {/* Notes */}
      {task.notes && (
        <p className="text-sm text-gray-500 mb-6 bg-gray-50 rounded-lg px-3 py-2">
          {task.notes}
        </p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => onComplete(task.id)}
          className="flex-1 flex items-center justify-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium rounded-xl py-3 transition-colors"
        >
          <Check className="w-4 h-4" strokeWidth={2.5} />
          Mark Complete
        </button>
        <button
          onClick={() => onEdit(task)}
          className="flex items-center justify-center gap-1.5 px-4 py-3 rounded-xl border border-[var(--border)] text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
        >
          Edit
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/dashboard/HeroTaskCard.tsx
git commit -m "feat: add HeroTaskCard component"
```

---

### Task 8: SecondaryTasks component (collapsed toggle)

**Files:**
- Create: `frontend/src/components/dashboard/SecondaryTasks.tsx`

**Step 1: Create SecondaryTasks**

```tsx
// frontend/src/components/dashboard/SecondaryTasks.tsx
"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Clock, Check } from "lucide-react";
import { Task } from "@/types";
import { cn } from "@/lib/utils";

interface SecondaryTasksProps {
  tasks: Task[];
  onComplete: (id: string) => void;
  onEdit: (task: Task) => void;
}

function formatDeadline(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const diff = Math.ceil((d.getTime() - Date.now()) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  if (diff < 0) return `${Math.abs(diff)}d overdue`;
  return `${diff}d`;
}

export function SecondaryTasks({ tasks, onComplete, onEdit }: SecondaryTasksProps) {
  const [open, setOpen] = useState(false);

  if (tasks.length === 0) return null;

  return (
    <div className="w-full">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-gray-700 transition-colors py-2"
      >
        {open ? (
          <ChevronUp className="w-4 h-4" />
        ) : (
          <ChevronDown className="w-4 h-4" />
        )}
        {open ? "Hide" : `Show ${tasks.length} more task${tasks.length > 1 ? "s" : ""}`}
      </button>

      {open && (
        <div className="flex flex-col gap-2 mt-1">
          {tasks.map((task) => (
            <div
              key={task.id}
              className="flex items-center gap-3 bg-white border border-[var(--border)] rounded-xl px-4 py-3 hover:border-gray-300 transition-colors group"
            >
              <button
                onClick={() => onComplete(task.id)}
                className="w-5 h-5 rounded-full border-2 border-gray-300 group-hover:border-emerald-400 flex items-center justify-center transition-colors shrink-0"
              >
                <Check className="w-3 h-3 text-transparent group-hover:text-emerald-400" strokeWidth={2.5} />
              </button>
              <button
                onClick={() => onEdit(task)}
                className="flex-1 text-left"
              >
                <p className="text-sm font-medium text-gray-800">{task.title}</p>
                {task.deadline && (
                  <p className="text-xs text-gray-400 flex items-center gap-1 mt-0.5">
                    <Clock className="w-3 h-3" />
                    {formatDeadline(task.deadline)}
                  </p>
                )}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/dashboard/SecondaryTasks.tsx
git commit -m "feat: add SecondaryTasks collapsed component"
```

---

### Task 9: TaskEditDrawer (side drawer like Linear)

**Files:**
- Create: `frontend/src/components/tasks/TaskEditDrawer.tsx`

**Step 1: Create TaskEditDrawer using shadcn Sheet**

```tsx
// frontend/src/components/tasks/TaskEditDrawer.tsx
"use client";

import { useState, useEffect } from "react";
import { X, Trash2 } from "lucide-react";
import { Task } from "@/types";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

interface TaskEditDrawerProps {
  task: Task | null;
  open: boolean;
  onClose: () => void;
  onSave: (updated: Task) => void;
  onDelete: (id: string) => void;
}

const EFFORT_LABELS: Record<number, string> = {
  1: "1 — Trivial", 2: "2", 3: "3 — Light",
  4: "4", 5: "5 — Medium", 6: "6",
  7: "7 — Heavy", 8: "8", 9: "9", 10: "10 — Brutal",
};

export function TaskEditDrawer({ task, open, onClose, onSave, onDelete }: TaskEditDrawerProps) {
  const [title, setTitle] = useState("");
  const [effort, setEffort] = useState<number>(5);
  const [deadline, setDeadline] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (task) {
      setTitle(task.title);
      setEffort(task.effort);
      setDeadline(task.deadline ? task.deadline.split("T")[0] : "");
      setNotes(task.notes ?? "");
    }
  }, [task]);

  function handleSave() {
    if (!task) return;
    onSave({
      ...task,
      title: title.trim(),
      effort: effort as Task["effort"],
      deadline: deadline ? new Date(deadline).toISOString() : null,
      notes: notes.trim() || null,
    });
    onClose();
  }

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent side="right" className="w-full sm:max-w-[420px] flex flex-col gap-0 p-0">
        <SheetHeader className="px-6 py-5 border-b border-[var(--border)]">
          <div className="flex items-center justify-between">
            <SheetTitle className="text-base font-semibold text-gray-900">Edit Task</SheetTitle>
            <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100 transition-colors">
              <X className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-6 py-6 flex flex-col gap-5">
          {/* Title */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">Title</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full text-sm text-gray-900 border border-[var(--border)] rounded-lg px-3 py-2.5 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100 transition"
              placeholder="What needs to be done?"
            />
          </div>

          {/* Effort */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
              Effort <span className="text-gray-400 normal-case">(1–10)</span>
            </label>
            <select
              value={effort}
              onChange={(e) => setEffort(Number(e.target.value))}
              className="w-full text-sm text-gray-900 border border-[var(--border)] rounded-lg px-3 py-2.5 outline-none focus:border-emerald-400 bg-white"
            >
              {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>{EFFORT_LABELS[n]}</option>
              ))}
            </select>
            {/* Visual bar */}
            <div className="flex gap-1 mt-1">
              {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                <div
                  key={n}
                  onClick={() => setEffort(n)}
                  className={`h-1.5 flex-1 rounded-full cursor-pointer transition-colors ${
                    n <= effort ? "bg-emerald-500" : "bg-gray-200"
                  }`}
                />
              ))}
            </div>
          </div>

          {/* Deadline */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">Deadline</label>
            <input
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="w-full text-sm text-gray-900 border border-[var(--border)] rounded-lg px-3 py-2.5 outline-none focus:border-emerald-400 bg-white"
            />
          </div>

          {/* Notes */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Any additional context..."
              className="w-full text-sm text-gray-900 border border-[var(--border)] rounded-lg px-3 py-2.5 outline-none focus:border-emerald-400 resize-none"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[var(--border)] flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={!title.trim()}
            className="flex-1 bg-emerald-500 hover:bg-emerald-600 disabled:bg-gray-100 disabled:cursor-not-allowed text-white disabled:text-gray-400 text-sm font-medium rounded-xl py-2.5 transition-colors"
          >
            Save changes
          </button>
          <button
            onClick={() => { onDelete(task!.id); onClose(); }}
            className="p-2.5 rounded-xl border border-[var(--border)] text-gray-400 hover:text-rose-500 hover:border-rose-200 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/tasks/TaskEditDrawer.tsx
git commit -m "feat: add TaskEditDrawer side panel"
```

---

### Task 10: Dashboard page

**Files:**
- Modify: `frontend/src/app/page.tsx` → redirect to `/dashboard`
- Create: `frontend/src/app/dashboard/page.tsx`
- Create: `frontend/src/app/layout.tsx` (update root layout)

**Step 1: Update root layout**

```tsx
// frontend/src/app/layout.tsx
import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist-sans" });

export const metadata: Metadata = {
  title: "NextMove — Do the one thing that matters",
  description: "AI-powered daily task prioritization for students",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={geist.variable}>
        {children}
      </body>
    </html>
  );
}
```

**Step 2: Create root redirect**

```tsx
// frontend/src/app/page.tsx
import { redirect } from "next/navigation";
export default function Home() {
  redirect("/dashboard");
}
```

**Step 3: Create Dashboard page**

```tsx
// frontend/src/app/dashboard/page.tsx
"use client";

import { useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { BrainDumpBar } from "@/components/dashboard/BrainDumpBar";
import { HeroTaskCard } from "@/components/dashboard/HeroTaskCard";
import { SecondaryTasks } from "@/components/dashboard/SecondaryTasks";
import { TaskEditDrawer } from "@/components/tasks/TaskEditDrawer";
import { MOCK_TASKS } from "@/lib/mock-data";
import { Task } from "@/types";

export default function DashboardPage() {
  const [tasks, setTasks] = useState<Task[]>(MOCK_TASKS);
  const [editTask, setEditTask] = useState<Task | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const primaryTask = tasks.find((t) => t.is_primary && t.state !== "completed");
  const secondaryTasks = tasks.filter((t) => !t.is_primary && t.state !== "completed").slice(0, 3);

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long", month: "long", day: "numeric",
  });

  function handleComplete(id: string) {
    setTasks((prev) =>
      prev.map((t) => (t.id === id ? { ...t, state: "completed" } : t))
    );
  }

  function handleEdit(task: Task) {
    setEditTask(task);
    setDrawerOpen(true);
  }

  function handleSave(updated: Task) {
    setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
  }

  function handleDelete(id: string) {
    setTasks((prev) => prev.filter((t) => t.id !== id));
  }

  function handleDump(text: string) {
    // Stub — will call POST /api/tasks/dump in real implementation
    console.log("Brain dump:", text);
  }

  return (
    <AppLayout>
      <div className="flex-1 flex flex-col max-w-2xl w-full mx-auto px-4 md:px-8 py-8 pb-24 md:pb-8 gap-6">
        {/* Date header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Good morning</h1>
          <p className="text-sm text-gray-500 mt-0.5">{today}</p>
        </div>

        {/* Brain dump */}
        <BrainDumpBar onSubmit={handleDump} />

        {/* Hero task */}
        {primaryTask ? (
          <HeroTaskCard
            task={primaryTask}
            onComplete={handleComplete}
            onEdit={handleEdit}
          />
        ) : (
          <div className="w-full bg-emerald-50 border border-emerald-200 rounded-2xl p-8 text-center">
            <p className="text-emerald-700 font-medium">You're all caught up!</p>
            <p className="text-sm text-emerald-600 mt-1">Add something new above.</p>
          </div>
        )}

        {/* Secondary tasks */}
        <SecondaryTasks
          tasks={secondaryTasks}
          onComplete={handleComplete}
          onEdit={handleEdit}
        />
      </div>

      {/* Task edit drawer */}
      <TaskEditDrawer
        task={editTask}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onSave={handleSave}
        onDelete={handleDelete}
      />
    </AppLayout>
  );
}
```

**Step 4: Commit**

```bash
git add frontend/src/app/layout.tsx frontend/src/app/page.tsx frontend/src/app/dashboard/page.tsx
git commit -m "feat: add dashboard page with hero task, secondary tasks, brain dump"
```

---

### Task 11: Tasks page (all tasks list)

**Files:**
- Create: `frontend/src/app/tasks/page.tsx`

**Step 1: Create Tasks page**

```tsx
// frontend/src/app/tasks/page.tsx
"use client";

import { useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { TaskEditDrawer } from "@/components/tasks/TaskEditDrawer";
import { MOCK_TASKS } from "@/lib/mock-data";
import { Task } from "@/types";
import { Check, Clock, Flame, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

const STATE_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-600",
  scheduled: "bg-blue-50 text-blue-700",
  in_progress: "bg-amber-50 text-amber-700",
  completed: "bg-emerald-50 text-emerald-700",
  missed: "bg-rose-50 text-rose-700",
  rescheduled: "bg-purple-50 text-purple-700",
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>(MOCK_TASKS);
  const [editTask, setEditTask] = useState<Task | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [filter, setFilter] = useState<"all" | "active" | "completed">("active");

  const filtered = tasks.filter((t) => {
    if (filter === "active") return t.state !== "completed";
    if (filter === "completed") return t.state === "completed";
    return true;
  });

  function handleComplete(id: string) {
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, state: "completed" } : t)));
  }
  function handleSave(updated: Task) {
    setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
  }
  function handleDelete(id: string) {
    setTasks((prev) => prev.filter((t) => t.id !== id));
  }

  return (
    <AppLayout>
      <div className="flex-1 flex flex-col max-w-2xl w-full mx-auto px-4 md:px-8 py-8 pb-24 md:pb-8 gap-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">All Tasks</h1>
          <button className="flex items-center gap-1.5 text-sm font-medium text-emerald-600 hover:text-emerald-700">
            <Plus className="w-4 h-4" />
            Add task
          </button>
        </div>

        {/* Filter tabs */}
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
          {(["active", "all", "completed"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "text-sm font-medium px-3 py-1.5 rounded-md capitalize transition-colors",
                filter === f ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
              )}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Task list */}
        <div className="flex flex-col gap-2">
          {filtered.length === 0 && (
            <div className="text-center py-12 text-gray-400 text-sm">No tasks here.</div>
          )}
          {filtered.map((task) => (
            <div
              key={task.id}
              className={cn(
                "flex items-center gap-3 bg-white border rounded-xl px-4 py-3 group transition-colors hover:border-gray-300",
                task.is_primary ? "border-emerald-200" : "border-[var(--border)]"
              )}
            >
              <button
                onClick={() => handleComplete(task.id)}
                className={cn(
                  "w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors shrink-0",
                  task.state === "completed"
                    ? "bg-emerald-500 border-emerald-500"
                    : "border-gray-300 group-hover:border-emerald-400"
                )}
              >
                <Check
                  className={cn(
                    "w-3 h-3 strokeWidth-2.5",
                    task.state === "completed" ? "text-white" : "text-transparent group-hover:text-emerald-400"
                  )}
                  strokeWidth={2.5}
                />
              </button>

              <button onClick={() => { setEditTask(task); setDrawerOpen(true); }} className="flex-1 text-left min-w-0">
                <p className={cn("text-sm font-medium", task.state === "completed" ? "line-through text-gray-400" : "text-gray-800")}>
                  {task.is_primary && (
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 mr-2 mb-0.5" />
                  )}
                  {task.title}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  {task.deadline && (
                    <span className="flex items-center gap-0.5 text-xs text-gray-400">
                      <Clock className="w-3 h-3" />
                      {new Date(task.deadline).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                    </span>
                  )}
                  <span className="flex items-center gap-0.5 text-xs text-gray-400">
                    <Flame className="w-3 h-3" />
                    {task.effort}
                  </span>
                </div>
              </button>

              <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full hidden sm:inline", STATE_COLORS[task.state])}>
                {task.state}
              </span>
            </div>
          ))}
        </div>
      </div>

      <TaskEditDrawer
        task={editTask}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onSave={handleSave}
        onDelete={handleDelete}
      />
    </AppLayout>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/app/tasks/page.tsx
git commit -m "feat: add Tasks page with filter tabs and list"
```

---

### Task 12: Calendar and Settings placeholder pages

**Files:**
- Create: `frontend/src/app/calendar/page.tsx`
- Create: `frontend/src/app/settings/page.tsx`

**Step 1: Create Calendar placeholder**

```tsx
// frontend/src/app/calendar/page.tsx
import { AppLayout } from "@/components/layout/AppLayout";
import { Calendar } from "lucide-react";

export default function CalendarPage() {
  return (
    <AppLayout>
      <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center px-8 pb-24 md:pb-8">
        <div className="w-16 h-16 rounded-2xl bg-emerald-50 flex items-center justify-center">
          <Calendar className="w-8 h-8 text-emerald-500" />
        </div>
        <h2 className="text-lg font-semibold text-gray-900">Calendar coming soon</h2>
        <p className="text-sm text-gray-500 max-w-xs">
          Connect your Google Calendar to see tasks scheduled alongside your events.
        </p>
        <button className="mt-2 bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium rounded-xl px-5 py-2.5 transition-colors">
          Connect Google Calendar
        </button>
      </div>
    </AppLayout>
  );
}
```

**Step 2: Create Settings placeholder**

```tsx
// frontend/src/app/settings/page.tsx
import { AppLayout } from "@/components/layout/AppLayout";
import { Settings } from "lucide-react";

export default function SettingsPage() {
  return (
    <AppLayout>
      <div className="flex-1 flex flex-col max-w-2xl w-full mx-auto px-4 md:px-8 py-8 pb-24 md:pb-8 gap-6">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

        <div className="flex flex-col gap-3">
          {[
            { label: "Notifications", desc: "Morning brief, reminders, nudges", badge: "8am" },
            { label: "Connected accounts", desc: "Google Calendar, Gmail", badge: null },
            { label: "Energy windows", desc: "Set your peak, mid, and low hours", badge: null },
            { label: "Account", desc: "Profile, password, sign out", badge: null },
          ].map(({ label, desc, badge }) => (
            <div
              key={label}
              className="flex items-center justify-between bg-white border border-[var(--border)] rounded-xl px-4 py-4 hover:border-gray-300 transition-colors cursor-pointer"
            >
              <div>
                <p className="text-sm font-medium text-gray-900">{label}</p>
                <p className="text-xs text-gray-500 mt-0.5">{desc}</p>
              </div>
              {badge && (
                <span className="text-xs font-medium bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full">
                  {badge}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </AppLayout>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/app/calendar/page.tsx frontend/src/app/settings/page.tsx
git commit -m "feat: add Calendar and Settings placeholder pages"
```

---

### Task 13: Onboarding tour (fullscreen, 3 steps)

**Files:**
- Create: `frontend/src/components/onboarding/OnboardingTour.tsx`
- Modify: `frontend/src/app/dashboard/page.tsx` (mount tour for first-time users)

**Step 1: Create OnboardingTour**

```tsx
// frontend/src/components/onboarding/OnboardingTour.tsx
"use client";

import { useState } from "react";
import { Zap, Brain, CheckCircle2, ChevronRight } from "lucide-react";

const STEPS = [
  {
    icon: Brain,
    title: "Dump everything on your mind",
    body: "Tasks, deadlines, assignments — don't organize, just type. NextMove figures out what matters.",
    cta: "Got it",
  },
  {
    icon: Zap,
    title: "We surface your #1 task",
    body: "Every morning, one primary task rises to the top. No decision fatigue. Just open the app and go.",
    cta: "Makes sense",
  },
  {
    icon: CheckCircle2,
    title: "Hit it, mark it done",
    body: "Complete your top task. The system learns, reschedules the rest, and resets for tomorrow.",
    cta: "Let's go",
  },
];

interface OnboardingTourProps {
  onComplete: () => void;
}

export function OnboardingTour({ onComplete }: OnboardingTourProps) {
  const [step, setStep] = useState(0);
  const current = STEPS[step];
  const Icon = current.icon;
  const isLast = step === STEPS.length - 1;

  return (
    <div className="fixed inset-0 bg-white z-50 flex flex-col items-center justify-center px-8">
      {/* Progress dots */}
      <div className="absolute top-8 flex gap-2">
        {STEPS.map((_, i) => (
          <div
            key={i}
            className={`h-1.5 rounded-full transition-all ${
              i === step ? "w-6 bg-emerald-500" : i < step ? "w-3 bg-emerald-300" : "w-3 bg-gray-200"
            }`}
          />
        ))}
      </div>

      {/* Content */}
      <div className="max-w-sm w-full text-center flex flex-col items-center gap-6">
        <div className="w-20 h-20 rounded-3xl bg-emerald-50 flex items-center justify-center">
          <Icon className="w-10 h-10 text-emerald-500" />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-3">{current.title}</h2>
          <p className="text-gray-500 leading-relaxed">{current.body}</p>
        </div>
        <button
          onClick={() => isLast ? onComplete() : setStep((s) => s + 1)}
          className="w-full flex items-center justify-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white font-semibold rounded-2xl py-4 text-base transition-colors"
        >
          {current.cta}
          {!isLast && <ChevronRight className="w-5 h-5" />}
        </button>
        {!isLast && (
          <button onClick={onComplete} className="text-sm text-gray-400 hover:text-gray-500">
            Skip tour
          </button>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Mount tour in Dashboard page**

In `frontend/src/app/dashboard/page.tsx`, add at the top of the component:

```tsx
const [showTour, setShowTour] = useState(true); // set to false after user completes
```

And add before the closing `</AppLayout>` tag:

```tsx
{showTour && <OnboardingTour onComplete={() => setShowTour(false)} />}
```

And add import:

```tsx
import { OnboardingTour } from "@/components/onboarding/OnboardingTour";
```

**Step 3: Commit**

```bash
git add frontend/src/components/onboarding/OnboardingTour.tsx frontend/src/app/dashboard/page.tsx
git commit -m "feat: add fullscreen onboarding tour"
```

---

### Task 14: Final build verification

**Step 1: Run the dev server and confirm no errors**

```bash
cd frontend && npm run dev
```

Expected: Server starts on http://localhost:3000, no TypeScript errors in terminal.

**Step 2: Run lint**

```bash
cd frontend && npm run lint
```

Expected: No errors.

**Step 3: Run production build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no type errors.

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete NextMove frontend MVP — dashboard, tasks, drawer, onboarding"
```

---

## Summary of Files Created

```
frontend/src/
├── types/index.ts
├── lib/mock-data.ts
├── app/
│   ├── layout.tsx              (updated)
│   ├── page.tsx                (redirect → /dashboard)
│   ├── globals.css             (updated with design tokens)
│   ├── dashboard/page.tsx
│   ├── tasks/page.tsx
│   ├── calendar/page.tsx
│   └── settings/page.tsx
└── components/
    ├── layout/
    │   ├── AppLayout.tsx
    │   ├── Sidebar.tsx
    │   └── BottomTabBar.tsx
    ├── dashboard/
    │   ├── BrainDumpBar.tsx
    │   ├── HeroTaskCard.tsx
    │   └── SecondaryTasks.tsx
    ├── tasks/
    │   └── TaskEditDrawer.tsx
    └── onboarding/
        └── OnboardingTour.tsx
```
