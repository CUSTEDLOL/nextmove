// frontend/src/types/index.ts

export type TaskState =
  | "pending"
  | "scheduled"
  | "in_progress"
  | "completed"
  | "missed"
  | "rescheduled";

export interface Step {
  id: string;
  title: string;
  state: TaskState;
}

export interface Task {
  id: string;
  title: string;
  effort: "low" | "medium" | "high";
  deadline: string | null; // ISO date string
  state: TaskState;
  priority_score: number; // 0–10
  is_primary: boolean;
  notes: string | null;
  created_at: string;
  steps?: Step[];
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
