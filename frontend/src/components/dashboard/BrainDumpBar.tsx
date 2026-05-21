"use client";

import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { ApiError } from "@/lib/api";

type BrainDumpSubmitResult = {
  createdCount: number;
  titles: string[];
};

interface BrainDumpBarProps {
  onSubmit?: (text: string) => Promise<BrainDumpSubmitResult>;
}

export function BrainDumpBar({ onSubmit }: BrainDumpBarProps) {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  function formatSuccessMessage(result: BrainDumpSubmitResult) {
    if (result.createdCount === 0) {
      return "Couldn't find any tasks in that. Try clearer action phrases or deadlines.";
    }
    const preview = result.titles.slice(0, 3).join(", ");
    const suffix = result.createdCount > 3 ? `, +${result.createdCount - 3} more` : "";
    return `Parsed ${result.createdCount} task${result.createdCount === 1 ? "" : "s"}: ${preview}${suffix}.`;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!value.trim()) return;
    setLoading(true);
    setFeedback(null);
    const trimmed = value.trim();

    try {
      const result = await onSubmit?.(trimmed);
      if (!result) {
        setFeedback({ type: "error", message: "Task dump did not return a result. Please try again." });
        return;
      }
      if (result.createdCount === 0) {
        setFeedback({ type: "error", message: formatSuccessMessage(result) });
        return;
      }
      setFeedback({ type: "success", message: formatSuccessMessage(result) });
      setValue("");
    } catch (error) {
      if (error instanceof ApiError && (error.code === "auth_required" || error.code === "unauthorized")) {
        setFeedback({ type: "error", message: "Your session expired. Please sign in again." });
        return;
      }
      if (error instanceof ApiError && error.code === "network") {
        setFeedback({ type: "error", message: "Couldn't reach the backend. Make sure the API is running." });
        return;
      }
      setFeedback({ type: "error", message: "Task dump failed. Please try again." });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-3 rounded-[var(--radius-md)] px-4 py-3.5 transition-all duration-150"
        style={{
          background: "var(--surface-elevated)",
          border: "1px solid var(--border)",
          boxShadow: "var(--shadow-card)",
        }}
        onFocusCapture={e => {
          (e.currentTarget as HTMLFormElement).style.borderColor = "var(--accent)";
          (e.currentTarget as HTMLFormElement).style.boxShadow = "0 0 0 3px rgba(27,107,72,0.1)";
        }}
        onBlurCapture={e => {
          // Only reset if focus is leaving the form entirely
          if (!e.currentTarget.contains(e.relatedTarget as Node)) {
            (e.currentTarget as HTMLFormElement).style.borderColor = "var(--border)";
            (e.currentTarget as HTMLFormElement).style.boxShadow = "var(--shadow-card)";
          }
        }}
      >
        <input
          type="text"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            if (feedback) setFeedback(null);
          }}
          placeholder='Try: "bio exam friday 2pm, 2 hours prep"'
          className="flex-1 text-sm bg-transparent outline-none"
          style={{
            color: "var(--foreground)",
            fontFamily: "var(--font-sans)",
          }}
          disabled={loading}
        />
        <button
          type="submit"
          disabled={!value.trim() || loading}
          className="w-7 h-7 rounded-[var(--radius-sm)] flex items-center justify-center transition-all duration-150 shrink-0 cursor-pointer disabled:cursor-not-allowed"
          style={{
            background: value.trim() && !loading ? "var(--accent)" : "var(--surface)",
            border: "1px solid var(--border)",
          }}
        >
          <ArrowRight
            className="w-3.5 h-3.5 transition-colors duration-150"
            style={{ color: value.trim() && !loading ? "#FFFFFF" : "var(--faint)" }}
          />
        </button>
      </form>

      {feedback && (
        <p
          className="text-xs px-1 transition-all duration-200"
          style={{
            color: feedback.type === "success" ? "var(--accent)" : "var(--destructive)",
            fontFamily: "var(--font-sans)",
          }}
        >
          {feedback.message}
        </p>
      )}
    </div>
  );
}
