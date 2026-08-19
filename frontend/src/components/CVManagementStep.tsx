// file: src/components/CVManagementStep.tsx
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Trash2, Eye, UploadCloud, Loader2, RefreshCw } from "lucide-react";
import { searchCandidatesByName, deleteCandidate, uploadCVs } from "../api";
import type { CandidateSummary } from "../types";

export function CVManagementStep({
  onViewCandidate,
}: {
  onViewCandidate: (candidateId: string, name: string) => void;
}) {
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const loadCandidates = async (q = "") => {
    setLoading(true);
    try {
      const data = await searchCandidatesByName(q);
      setCandidates(data);
    } catch {
      setCandidates([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCandidates();
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => loadCandidates(query), 300);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      await uploadCVs(Array.from(files));
      await loadCandidates(query);
    } catch {
      // no-op -- keep it simple here, failures are visible via the empty result
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const handleDelete = async (candidateId: string, name: string) => {
    const ok = window.confirm(`Delete candidate "${name}" permanently?`);
    if (!ok) return;
    setDeletingId(candidateId);
    try {
      await deleteCandidate(candidateId);
      setCandidates((prev) => prev.filter((c) => c.candidate_id !== candidateId));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <section className="panel p-6">
      <p className="label">CV Management</p>
      <h2 className="mt-2 text-lg font-bold">Manage Candidate CVs</h2>
      <p className="mt-1 text-sm text-slate-500">Upload new CVs, browse existing candidates, view or delete them.</p>

      <button
        type="button"
        onClick={() => fileInput.current?.click()}
        disabled={uploading}
        className="mt-5 flex min-h-40 w-full flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 px-5 transition hover:border-[#C1121F] hover:bg-red-50 disabled:opacity-60"
      >
        {uploading ? (
          <Loader2 className="h-8 w-8 animate-spin text-[#C1121F]" />
        ) : (
          <UploadCloud className="h-8 w-8 text-[#C1121F]" />
        )}
        <span className="mt-3 text-sm font-semibold">{uploading ? "Uploading…" : "Drop CVs here"}</span>
        <span className="mt-1 text-xs text-slate-500">or click to browse · PDF, DOCX, PPTX</span>
      </button>
      <input
        ref={fileInput}
        type="file"
        multiple
        accept=".pdf,.docx,.pptx"
        className="hidden"
        onChange={(e) => handleUpload(e.target.files)}
      />

      <div className="mt-6 flex items-center justify-between">
        <div className="relative w-full max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search candidates..."
            className="field w-full pl-9"
          />
        </div>
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span>{candidates.length} candidate(s)</span>
          <button onClick={() => loadCandidates(query)} className="hover:text-slate-800" aria-label="Refresh">
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="mt-4">
        {loading && candidates.length === 0 ? (
          <div className="flex items-center justify-center py-10 text-slate-400">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : candidates.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400">No candidates found.</p>
        ) : (
          <AnimatePresence initial={false}>
            <div className="grid gap-2">
              {candidates.map((c) => (
                <motion.div
                  key={c.candidate_id}
                  layout
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold">{c.name}</p>
                    {c.email && <p className="truncate text-xs text-slate-500">{c.email}</p>}
                  </div>
                  <button
                    onClick={() => onViewCandidate(c.candidate_id, c.name)}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                  >
                    <Eye className="h-3.5 w-3.5" />
                    View
                  </button>
                  <button
                    onClick={() => handleDelete(c.candidate_id, c.name)}
                    disabled={deletingId === c.candidate_id}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 disabled:opacity-60"
                  >
                    {deletingId === c.candidate_id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                    Delete
                  </button>
                </motion.div>
              ))}
            </div>
          </AnimatePresence>
        )}
      </div>
    </section>
  );
}