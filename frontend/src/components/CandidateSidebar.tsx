// file: src/components/CandidateSidebar.tsx
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Trash2, Eye, UploadCloud, Loader2, RefreshCw, Check } from "lucide-react";
import { searchCandidatesByName, deleteCandidate, uploadCVs } from "../api";
import type { CandidateSummary, Step } from "../types";



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
  return (
    <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="p-4">
        <p className="label">Workflow</p>
        <nav className="mt-2 space-y-1">
          {steps.map((s, i) => {
            const active = s.key === currentStep;
            return (
              <button
                key={s.key}
                onClick={() => onStepChange(s.key)}
                className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold transition ${
                  active ? "bg-[#C1121F] text-white" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] font-bold ${
                  active ? "bg-white/20" : "bg-slate-100 text-slate-400"
                }`}>
                  {i + 1}
                </span>
                {s.label}
              </button>
            );
          })}
        </nav>
      </div>
    </aside>
  );
}