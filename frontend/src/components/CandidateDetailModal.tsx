import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Trash2, Briefcase, GraduationCap, Languages, Award, Globe, FolderOpen, FileText, AlertCircle, Mail, Phone, Link, GitBranch } from "lucide-react";
import { getCandidateDetail, deleteCandidate } from "../api";

const HIDDEN_KEYS = new Set(["__v", "_id", "candidate_id", "id", "createdAt", "updatedAt", "embedding", "vector", "normalized_name"]);

export function CandidateDetailModal({
  candidateId,
  name,
  onClose,
}: {
  candidateId: string;
  name: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setData(null);
    getCandidateDetail(candidateId)
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load candidate");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [candidateId]);

  const handleDelete = async () => {
    if (!confirm(`Permanently delete ${name}? This cannot be undone.`)) return;
    try {
      await deleteCandidate(candidateId);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  if (!data) return null;

  const summary = data.summary as string | undefined;
  const email = data.email as string | undefined;
  const phone = data.phone as string | undefined;
  const linkedin = data.linkedin as string | undefined;
  const github = data.github as string | undefined;
  const skills = (data.skills as string[]) || [];
  const languages = (data.languages as unknown[]) || [];
  const education = (data.education as unknown[]) || [];
  const certifications = (data.certifications as Record<string, unknown>[]) || [];
  const countries = (data.countries_worked as string[]) || [];
  const affiliations = (data.professional_affiliations as string[]) || [];
  const expertise = (data.expertise_areas as Record<string, unknown>[]) || [];
  const functionalSkills = (data.functional_skills as Record<string, unknown>[]) || [];
  const experiences = (data.experience as Record<string, unknown>[]) || [];
  const projects = (data.projects as Record<string, unknown>[]) || [];

  const renderExpertise = (items: Record<string, unknown>[], icon: React.ReactNode, title: string) => {
    if (!items.length) return null;
    return (
      <div className="rounded-xl border border-slate-200 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">{icon} {title}</div>
        <div className="mt-3 space-y-2">
          {items.map((raw, i) => (
            <div key={i} className="rounded-lg border border-slate-100 bg-white p-3">
              <p className="text-sm font-semibold">{String(raw.category || "")}</p>
              {raw.description ? <p className="mt-1 text-xs text-slate-600 ">{String(raw.description)}</p> : null}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderCertifications = (items: Record<string, unknown>[]) => {
    if (!items.length) return null;
    return (
      <div className="rounded-xl border border-slate-200 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700"><Award className="h-4 w-4" /> Certifications</div>
        <div className="mt-3 space-y-2">
          {items.map((cert, i) => (
            <div key={i} className="rounded-lg border border-slate-100 bg-white p-3">
              <p className="text-sm font-semibold">{String(cert.name || "")}</p>
              <p className="text-xs text-slate-500">{String(cert.issuer || "")}{cert.year ? ` · ${String(cert.year)}` : ""}</p>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderStringList = (items: string[], icon: React.ReactNode, title: string) => {
    if (!items.length) return null;
    return (
      <div className="rounded-xl border border-slate-200 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">{icon} {title}</div>
        <ul className="mt-2 list-disc pl-5 text-sm text-slate-700">
          {items.map((s, i) => <li key={i}>{s}</li>)}
        </ul>
      </div>
    );
  };

  const renderBadges = (items: string[], icon: React.ReactNode, title: string) => {
    if (!items.length) return null;
    return (
      <div className="rounded-xl border border-slate-200 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">{icon} {title}</div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {items.map((s, i) => (
            <span key={i} className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">{s}</span>
          ))}
        </div>
      </div>
    );
  };

  const renderEducation = () => {
    if (!education.length) return null;
    return (
      <div className="rounded-xl border border-slate-200 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700"><GraduationCap className="h-4 w-4" /> Education</div>
        <div className="mt-3 space-y-3">
          {education.map((ed, i) => {
            const raw = ed as Record<string, unknown>;
            return (
              <div key={i} className="rounded-lg border border-slate-100 bg-white p-3">
                <p className="text-sm font-semibold">{String(raw.degree || "")}{raw.field_of_study ? ` in ${String(raw.field_of_study)}` : ""}</p>
                <p className="text-xs text-slate-500">{String(raw.institution || "")}{raw.years ? ` · ${String(raw.years)}` : ""}</p>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderLanguages = () => {
    if (!languages.length) return null;
    return (
      <div className="rounded-xl border border-slate-200 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700"><Languages className="h-4 w-4" /> Languages</div>
        <div className="mt-2 flex flex-wrap gap-2">
          {languages.map((lang, i) => {
            const raw = lang as Record<string, unknown>;
            return (
              <span key={i} className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                {String(raw.language || "")} <span className="text-slate-500">· {String(raw.level || "")}</span>
              </span>
            );
          })}
        </div>
      </div>
    );
  };

  const renderExperience = () => {
    if (!experiences.length) return null;
    return (
      <div className="rounded-xl border border-slate-200 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700"><Briefcase className="h-4 w-4" /> Experience</div>
        <div className="mt-3 space-y-3">
           {experiences.map((exp, i) => {
             const raw = exp as Record<string, unknown>;
             const responsibilities = (raw.responsibilities as unknown[]) || [];
             const deliverables = (raw.deliverables as string[]) || [];
             const technologies = (raw.technologies as string[]) || [];
             return (
               <div key={i} className="rounded-lg border border-slate-200   bg-white p-3">
                 <div className="flex items-center justify-between">
                   <p className="text-sm font-semibold">{String(raw.title || "")}</p>
                   {raw.dates ? <span className="text-xs text-slate-500">{String(raw.dates)}</span> : null}
                 </div>
                 <p className="text-xs text-slate-500">{String(raw.company || "")}</p>
                 {raw.description ? <p className="mt-1 text-sm text-slate-600">{String(raw.description)}</p> : null}
                 {responsibilities.length > 0 && (
                   <div className="mt-2">
                     <p className="text-xs font-semibold text-slate-500">Responsibilities</p>
                     <ul className="mt-1 list-disc pl-5 text-xs text-slate-600">
                       {responsibilities.map((r, j) => {
                         const resp = r as Record<string, unknown>;
                         return <li key={j}>{String(resp.description || resp.category || JSON.stringify(r))}</li>;
                       })}
                     </ul>
                   </div>
                 )}
                 {deliverables.length > 0 && (
                   <div className="mt-2">
                     <p className="text-xs font-semibold text-slate-500">Deliverables</p>
                     <ul className="mt-1 list-disc pl-5 text-xs text-slate-600">
                       {deliverables.map((r, j) => <li key={j}>{String(r)}</li>)}
                     </ul>
                   </div>
                 )}
                 {technologies.length > 0 && (
                   <div className="mt-2 flex flex-wrap gap-1">
                     {technologies.map((t, j) => (
                       <span key={j} className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">{String(t)}</span>
                     ))}
                   </div>
                 )}
               </div>
             );
           })}
        </div>
      </div>
    );
  };

  const renderProjects = () => {
    if (!projects.length) return null;
    return (
      <div className="rounded-xl border border-slate-200 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700"><FolderOpen className="h-4 w-4" /> Projects</div>
        <div className="mt-3 space-y-2">
          {projects.map((proj, i) => {
            const raw = proj as Record<string, unknown>;
            const technologies = (raw.technologies as string[]) || [];
            return (
              <div key={i} className="rounded-lg border border-slate-100 bg-white p-3">
                <p className="text-sm font-semibold">{String(raw.name || `Project ${i + 1}`)}</p>
                {raw.description ? <p className="mt-1 text-sm text-slate-600">{String(raw.description)}</p> : null}
                {technologies.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {technologies.map((t, j) => (
                      <span key={j} className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">{String(t)}</span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderContact = () => {
    const items: { icon: React.ReactNode; label: string; value: string }[] = [];
    if (email) items.push({ icon: <Mail className="h-3.5 w-3.5" />, label: "Email", value: email });
    if (phone) items.push({ icon: <Phone className="h-3.5 w-3.5" />, label: "Phone", value: phone });
    if (linkedin) items.push({ icon: <Link className="h-3.5 w-3.5" />, label: "LinkedIn", value: linkedin });
    if (github) items.push({ icon: <GitBranch className="h-3.5 w-3.5" />, label: "GitHub", value: github });
    if (!items.length) return null;
    return (
      <div className="rounded-xl border border-slate-200 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">Contact</div>
        <div className="mt-2 space-y-1">
          {items.map((item, i) => (
            <div key={i} className="flex items-center gap-2 text-sm text-slate-700">
              {item.icon} <span className="text-xs font-semibold text-slate-500 w-16">{item.label}</span> {item.value}
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 p-4 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onMouseDown={onClose}
      >
        <motion.div
          initial={{ scale: 0.96, y: 10 }}
          animate={{ scale: 1, y: 0 }}
          exit={{ scale: 0.96, y: 10 }}
          onMouseDown={(e) => e.stopPropagation()}
          className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="label">Candidate profile</p>
              <h2 className="mt-1 text-2xl font-bold">{name}</h2>
            </div>
            <div className="flex gap-1">
              <button onClick={handleDelete} className="rounded-lg p-2 text-red-500 hover:bg-red-50" aria-label="Delete candidate">
                <Trash2 className="h-5 w-5" />
              </button>
              <button onClick={onClose} className="rounded-lg p-2 hover:bg-slate-100">
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          {loading && (
            <div className="mt-6 flex items-center gap-2 text-sm text-slate-500">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-[#C1121F]" /> Loading…
            </div>
          )}

          {error && !loading && (
            <div className="mt-6 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="font-semibold">Failed to load candidate</p>
                <p className="mt-1">{error}</p>
              </div>
            </div>
          )}

          {!loading && !error && data && (
            <div className="mt-4 space-y-4">
              {renderContact()}
              {summary && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-700"><FileText className="h-4 w-4" /> Summary</div>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{summary}</p>
                </div>
              )}
              {renderBadges(skills, <Award className="h-4 w-4" />, "Skills")}
              {renderExpertise(functionalSkills, <Award className="h-4 w-4" />, "Functional Skills")}
              {renderExpertise(expertise, <Briefcase className="h-4 w-4" />, "Expertise Areas")}
              {renderLanguages()}
              {renderBadges(countries, <Globe className="h-4 w-4" />, "Countries Worked")}
              {renderCertifications(certifications)}
              {renderStringList(affiliations, <Globe className="h-4 w-4" />, "Professional Affiliations")}
              {renderEducation()}
              {renderExperience()}
              {renderProjects()}

              {Object.entries(data)
                .filter(([k]) => !HIDDEN_KEYS.has(k))
                .map(([k, v]) => {
                  if (["summary", "skills", "functional_skills", "expertise_areas", "languages", "countries_worked", "certifications", "professional_affiliations", "education", "experience", "projects"].includes(k)) return null;
                  if (v === null || v === undefined || v === "") return null;
                  if (Array.isArray(v)) {
                    if (v.length === 0) return null;
                    return (
                      <div key={k} className="rounded-xl border border-slate-200 p-4">
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{k}</p>
                        <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
                          {v.map((item, i) => (
                            <li key={i}>{typeof item === "object" ? JSON.stringify(item) : String(item)}</li>
                          ))}
                        </ul>
                      </div>
                    );
                  }
                  if (typeof v === "object") {
                    return (
                      <div key={k} className="rounded-xl border border-slate-200 p-4">
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{k}</p>
                        <pre className="mt-1 rounded-lg bg-slate-50 p-3 text-xs text-slate-700 overflow-x-auto">
                          {JSON.stringify(v, null, 2)}
                        </pre>
                      </div>
                    );
                  }
                  return (
                    <div key={k} className="rounded-xl border border-slate-200 p-4">
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{k}</p>
                      <p className="text-sm text-slate-700">{String(v)}</p>
                    </div>
                  );
                })}
            </div>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
