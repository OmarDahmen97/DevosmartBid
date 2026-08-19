import { useState } from "react";
import type { Step } from "../types";

const steps: { key: Step; label: string }[] = [
  { key: "cv_management", label: "CV Management" },
  { key: "matching", label: "Match & Select" },
  { key: "review", label: "Review" },
  { key: "generation", label: "Generate" },
];

export function CandidateSidebar({
  currentStep,
  onStepChange,
}: {
  currentStep: Step;
  onStepChange: (step: Step) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <aside className="bg-white border-slate-200 md:sticky md:top-0 md:h-screen md:w-56 lg:w-64 md:border-r">
      {/* Mobile Header */}
      <div className="flex items-center justify-between border-b p-4 md:hidden">
        <span className="font-semibold">Workflow</span>

        <button
          onClick={() => setOpen(!open)}
          className="rounded-lg p-2 hover:bg-slate-100"
        >
          ☰
        </button>
      </div>

      {/* Navigation */}
      <div className={`${open ? "block" : "hidden"} md:block`}>
        <div className="p-4">
          <p className="label">Workflow</p>

          <nav className="mt-2 space-y-1">
            {steps.map((s, i) => {
              const active = s.key === currentStep;

              return (
                <button
                  key={s.key}
                  onClick={() => {
                    onStepChange(s.key);
                    setOpen(false);
                  }}
                  className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold transition ${
                    active
                      ? "bg-[#C1121F] text-white"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <span
                    className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] font-bold ${
                      active
                        ? "bg-white/20"
                        : "bg-slate-100 text-slate-400"
                    }`}
                  >
                    {i + 1}
                  </span>

                  {s.label}
                </button>
              );
            })}
          </nav>
        </div>
      </div>
    </aside>
  );
}