// frontend/src/lib/mock-data.ts
import { Task } from "@/types";

export const MOCK_TASKS: Task[] = [
  {
    id: "1",
    title: "Write literature review for CS thesis",
    effort: "high",
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
    effort: "medium",
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
    effort: "low",
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
    effort: "medium",
    deadline: new Date(Date.now() + 432000000).toISOString(), // 5 days
    state: "pending",
    priority_score: 6.4,
    is_primary: false,
    notes: null,
    created_at: new Date().toISOString(),
  },
];
