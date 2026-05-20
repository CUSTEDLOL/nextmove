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
