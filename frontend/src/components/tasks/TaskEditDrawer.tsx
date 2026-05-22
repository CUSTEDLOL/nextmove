"use client";

import { useState } from "react";
import { X, Trash2 } from "lucide-react";
import { Task } from "@/types";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { TimeEstimatePicker } from "@/components/shared/TimeEstimatePicker";

interface TaskEditDrawerProps {
  task: Task | null;
  open: boolean;
  onClose: () => void;
  onSave: (updated: Task) => void;
  onDelete: (id: string) => void;
}

function TaskEditDrawerInner({ task, onClose, onSave, onDelete }: Omit<TaskEditDrawerProps, "open">) {
  const [title, setTitle] = useState(task?.title ?? "");
  const [effort, setEffort] = useState<Task["effort"]>(task?.effort ?? "medium");
  const [deadline, setDeadline] = useState(
    task?.deadline ? task.deadline.split("T")[0] : ""
  );
  const [notes, setNotes] = useState(task?.notes ?? "");

  function handleSave() {
    if (!task) return;
    onSave({
      ...task,
      title: title.trim(),
      effort,
      deadline: deadline ? new Date(deadline).toISOString() : null,
      notes: notes.trim() || null,
    });
    onClose();
  }

  return (
    <>
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

        {/* Time estimate */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
            Time estimate
          </label>
          <TimeEstimatePicker value={effort} onChange={setEffort} />
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
    </>
  );
}

export function TaskEditDrawer({ task, open, onClose, onSave, onDelete }: TaskEditDrawerProps) {
  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent side="bottom" className="rounded-t-2xl flex flex-col gap-0 p-0 max-h-[90vh]">
        {task && (
          <TaskEditDrawerInner
            key={task.id}
            task={task}
            onClose={onClose}
            onSave={onSave}
            onDelete={onDelete}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}
