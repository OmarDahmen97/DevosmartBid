import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, ChevronDown, ChevronUp, AlertTriangle } from "lucide-react";
import { generateAdaptedCV } from "../api";
import type { GenerationResponse, SelectionEntry } from "../types";

type SectionKey = "summary" | "skills" | "expertise_areas" | "functional_skills" | "education" | "certifications" | "languages" | "countries_worked" | "professional_affiliations";

export function GenerationStep({
  missionText,
  reviewSelections,
  selection,
  onBack,
}: {
  missionText: string;
  reviewSelections: Record<string, { selected_experience_indices: number[]; selected_project_indices: number[] }>;
  selection: SelectionEntry[];
  onBack: () => void;
}) {
  const [targetLanguage, setTargetLanguage] = useState("English");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GenerationResponse | null>(null);
  const [error, setError] = useState("");

  const generate = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const candidates = selection
        .filter((s) => reviewSelections[s.candidate_id])
        .map((s) => ({
          candidate_id: s.candidate_id,
          selected_experience_indices: reviewSelections[s.candidate_id].selected_experience_indices,
          selected_project_indices: reviewSelections[s.candidate_id].selected_project_indices,
        }));
      const data = await generateAdaptedCV(missionText, targetLanguage, candidates);
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  };

  const StaticBlock = ({ title, content }: { title: string; content: React.ReactNode }) => {
    const [open, setOpen] = useState(true);
    return (
      <div className="rounded-xl border border-slate-200 bg-white">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center justify-between rounded-t-xl border-b border-slate-100 bg-slate-50 px-4 py-3 text-left"
        >
          <span className="text-sm font-semibold">{title}</span>
          {open ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
        </button>
        {open && <div className="p-4 text-sm leading-6 text-slate-600">{content}</div>}
      </div>
    );
  };

  return (
    <section className="panel p-6">
      <p className="label">Step 4 — Generate Adapted CV</p>
      <h2 className="mt-2 text-lg font-bold">Generate Mission-Tailored Content</h2>
      <p className="mt-1 text-sm text-slate-500">LLM rewrites selected experiences/projects for the mission. Template export coming soon.</p>

      {!result && (
        <div className="mt-4">
          <label className="block text-sm font-semibold">Target Language</label>
          <select
            value={targetLanguage}
            onChange={(e) => setTargetLanguage(e.target.value)}
            className="field mt-1 w-full max-w-sm"
          >
            <option>English</option>
            <option>French</option>
            <option>Spanish</option>
            <option>German</option>
          </select>
          <button
            onClick={generate}
            disabled={loading}
            className="mt-4 inline-flex items-center gap-2 rounded-xl bg-[#C1121F] px-5 py-2.5 text-sm font-bold text-white disabled:opacity-70"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {loading ? "Generating…" : "Generate"}
          </button>
        </div>
      )}

      <AnimatePresence>
        {error && (
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 text-sm text-red-600">
            {error}
          </motion.p>
        )}
      </AnimatePresence>

      {result && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-6 space-y-6">
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-semibold">Template export not yet available</p>
              <p className="mt-1">{result.message}</p>
            </div>
          </div>

          {result.results.map((r) => {
            const content = r.generated_content;
            return (
              <div key={r.candidate_id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Candidate</p>
                    <h3 className="text-xl font-bold">{r.name}</h3>
                  </div>
                  <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-700">Generated</span>
                </div>

                <div className="mt-4 grid gap-3">
                  <StaticBlock title="Summary" content={<p>{content.summary}</p>} />
                  <StaticBlock title="Skills" content={<p className="line-clamp-4">{Array.isArray(content.skills) ? content.skills.join(", ") : ""}</p>} />
                  <StaticBlock title="Expertise Areas" content={<p>{Array.isArray(content.expertise_areas) ? content.expertise_areas.join(", ") : ""}</p>} />
                  <StaticBlock title="Functional Skills" content={<p>{Array.isArray(content.functional_skills) ? content.functional_skills.join(", ") : ""}</p>} />
                  <StaticBlock title="Education" content={<ul className="list-disc pl-5">{content.education.map((e, i) => <li key={i}>{e}</li>)}</ul>} />
                  <StaticBlock title="Certifications" content={<ul className="list-disc pl-5">{content.certifications.map((e, i) => <li key={i}>{e}</li>)}</ul>} />
                  <StaticBlock title="Languages" content={<p>{content.languages.join(", ")}</p>} />
                  <StaticBlock title="Countries Worked" content={<p>{content.countries_worked.join(", ")}</p>} />
                  <StaticBlock title="Professional Affiliations" content={<p>{content.professional_affiliations.join(", ")}</p>} />

                  <div className="rounded-xl border border-slate-200 bg-white">
                    <div className="border-b border-slate-100 bg-slate-50 px-4 py-3">
                      <p className="text-sm font-semibold">Experience</p>
                    </div>
                    <div className="p-3 space-y-2">
                      {content.experience.map((exp, i) => (
                        <div key={i} className="rounded-lg border border-slate-200 p-3">
                          <div className="flex items-center justify-between">
                            <p className="text-sm font-semibold">{exp.title} · {exp.company}</p>
                            {exp._adapted === false && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                                <AlertTriangle className="h-3 w-3" /> Original
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-500">{exp.dates}</p>
                          <p className="mt-1 text-sm text-slate-700">{exp.description}</p>
                          {exp.responsibilities && (
                            <ul className="mt-2 list-disc pl-5 text-xs text-slate-600">
                              {exp.responsibilities.map((r, j) => <li key={j}>{r}</li>)}
                            </ul>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-white">
                    <div className="border-b border-slate-100 bg-slate-50 px-4 py-3">
                      <p className="text-sm font-semibold">Projects</p>
                    </div>
                    <div className="p-3 space-y-2">
                      {content.projects.map((proj, i) => (
                        <div key={i} className="rounded-lg border border-slate-200 p-3">
                          <div className="flex items-center justify-between">
                            <p className="text-sm font-semibold">{proj.name}</p>
                            {proj._adapted === false && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                                <AlertTriangle className="h-3 w-3" /> Original
                              </span>
                            )}
                          </div>
                          <p className="mt-1 text-sm text-slate-700">{proj.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </motion.div>
      )}

      <div className="mt-6 flex items-center justify-between">
        <button onClick={onBack} className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold hover:bg-slate-50">
          Back
        </button>
        {result && (
          <button
            onClick={() => {
              setResult(null);
              onBack();
            }}
            className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold hover:bg-slate-50"
          >
            Start Over
          </button>
        )}
      </div>
    </section>
  );
}
