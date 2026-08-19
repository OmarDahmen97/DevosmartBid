// file: src/components/CVManagementStep.tsx

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    Search,
    Trash2,
    Eye,
    UploadCloud,
    Loader2,
    RefreshCw,
} from "lucide-react";

import {
    searchCandidatesByName,
    deleteCandidate,
    uploadCVs,
} from "../api";

import type {
    CandidateSummary,
    UploadResultItem,
    UploadErrorItem,
} from "../types";

const statusStyles: Record<string, string> = {
    new_candidate:
        "border-emerald-200 bg-emerald-50 text-emerald-700",
    new_version:
        "border-amber-200 bg-amber-50 text-amber-700",
    duplicate:
        "border-slate-200 bg-slate-50 text-slate-600",
};

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

    const [pendingFiles, setPendingFiles] = useState<File[]>([]);

    const [results, setResults] = useState<
        (UploadResultItem | UploadErrorItem)[]
    >([]);

    const fileInput = useRef<HTMLInputElement>(null);

    // ============================================================
    // LOAD CANDIDATES
    // ============================================================

    const loadCandidates = async (q = "") => {
        setLoading(true);

        try {
            const data = await searchCandidatesByName(q);
            setCandidates(data);
        } catch (error) {
            console.error("Failed to load candidates:", error);
            setCandidates([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadCandidates("");
    }, []);

    useEffect(() => {
        const timeout = setTimeout(() => {
            loadCandidates(query);
        }, 300);

        return () => clearTimeout(timeout);

        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [query]);

    // ============================================================
    // SELECT FILES
    // ============================================================

    const addFiles = (files: FileList | null) => {
        if (!files || files.length === 0) return;

        const incoming = Array.from(files);

        setPendingFiles((prev) => {
            const names = new Set(prev.map((file) => file.name));

            const uniqueFiles = incoming.filter(
                (file) => !names.has(file.name)
            );

            return [...prev, ...uniqueFiles];
        });
    };

    const removePendingFile = (name: string) => {
        setPendingFiles((prev) =>
            prev.filter((file) => file.name !== name)
        );
    };

    // ============================================================
    // EXTRACT
    // ============================================================

    const handleExtract = async () => {
        if (pendingFiles.length === 0) return;

        setUploading(true);
        setResults([]);

        try {
            console.log(
                "Uploading files:",
                pendingFiles.map((file) => file.name)
            );

            const data = await uploadCVs(pendingFiles);

            console.log("Extraction result:", data);

            // Display extraction results
            setResults(data.results || []);

            // Clear selected files
            setPendingFiles([]);

            // Refresh candidates
            await loadCandidates("");
        } catch (error) {
            console.error("Extraction error:", error);

            setResults([
                {
                    filename: "",
                    error:
                        error instanceof Error
                            ? error.message
                            : "Unknown error",
                },
            ]);
        } finally {
            setUploading(false);

            if (fileInput.current) {
                fileInput.current.value = "";
            }
        }
    };

    // ============================================================
    // DELETE CANDIDATE
    // ============================================================

    const handleDelete = async (
        candidateId: string,
        name: string
    ) => {
        const ok = window.confirm(
            `Delete candidate "${name}" permanently?`
        );

        if (!ok) return;

        setDeletingId(candidateId);

        try {
            await deleteCandidate(candidateId);

            setCandidates((prev) =>
                prev.filter(
                    (candidate) =>
                        candidate.candidate_id !== candidateId
                )
            );
        } catch (error) {
            console.error("Failed to delete candidate:", error);
            alert("Failed to delete candidate.");
        } finally {
            setDeletingId(null);
        }
    };

    // ============================================================
    // RENDER
    // ============================================================

    return (
        <section className="panel p-6">

            {/* ================================================== */}
            {/* HEADER */}
            {/* ================================================== */}

            <p className="label">CV Management</p>

            <h2 className="mt-2 text-lg font-bold">
                Manage Candidate CVs
            </h2>

            <p className="mt-1 text-sm text-slate-500">
                Upload new CVs, browse existing candidates, view or
                delete them.
            </p>

            {/* ================================================== */}
            {/* UPLOAD AREA */}
            {/* ================================================== */}

            <button
                type="button"
                onClick={() => fileInput.current?.click()}
                disabled={uploading}
                className="mt-5 flex min-h-40 w-full flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 px-5 transition hover:border-[#C1121F] hover:bg-red-50 disabled:opacity-60"
            >
                <UploadCloud className="h-8 w-8 text-[#C1121F]" />

                <span className="mt-3 text-sm font-semibold">
                    Drop CVs here
                </span>

                <span className="mt-1 text-xs text-slate-500">
                    or click to browse · PDF, DOCX, PPTX
                </span>
            </button>

            <input
                ref={fileInput}
                type="file"
                multiple
                accept=".pdf,.docx,.pptx"
                className="hidden"
                onChange={(e) => {
                    addFiles(e.target.files);

                    // Allow selecting the same file again
                    e.target.value = "";
                }}
            />

            {/* ================================================== */}
            {/* SELECTED FILES */}
            {/* ================================================== */}

            {pendingFiles.length > 0 && (
                <div className="mt-4 space-y-2">

                    <div className="flex items-center justify-between">
                        <p className="text-sm font-semibold">
                            {pendingFiles.length} file(s) selected
                        </p>

                        <button
                            type="button"
                            onClick={() => setPendingFiles([])}
                            className="text-xs font-medium text-[#C1121F]"
                        >
                            Clear all
                        </button>
                    </div>

                    {pendingFiles.map((file) => (
                        <div
                            key={file.name}
                            className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2.5 text-sm"
                        >
                            <span className="min-w-0 flex-1 truncate font-medium">
                                {file.name}
                            </span>

                            <button
                                type="button"
                                onClick={() =>
                                    removePendingFile(file.name)
                                }
                                aria-label={`Remove ${file.name}`}
                            >
                                <Trash2 className="h-4 w-4 text-slate-400" />
                            </button>
                        </div>
                    ))}

                    {/* ================================================== */}
                    {/* EXTRACT BUTTON */}
                    {/* ================================================== */}

                    <button
                        type="button"
                        onClick={handleExtract}
                        disabled={uploading}
                        className="mt-2 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#C1121F] px-4 py-2.5 text-sm font-bold text-white disabled:opacity-70"
                    >
                        {uploading && (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        )}

                        {uploading
                            ? "Extracting…"
                            : "Upload & Extract"}
                    </button>
                </div>
            )}

            {/* ================================================== */}
            {/* EXTRACTION RESULTS */}
            {/* ================================================== */}

            <AnimatePresence>
                {results.length > 0 && (
                    <motion.div
                        initial={{
                            opacity: 0,
                            y: 8,
                        }}
                        animate={{
                            opacity: 1,
                            y: 0,
                        }}
                        exit={{
                            opacity: 0,
                            y: 8,
                        }}
                        className="mt-5 space-y-3"
                    >
                        <div className="flex items-center justify-between">
                            <p className="text-sm font-semibold">
                                Extraction Results
                            </p>

                            <button
                                type="button"
                                onClick={() => setResults([])}
                                className="text-xs font-medium text-slate-400 hover:text-slate-700"
                            >
                                Clear
                            </button>
                        </div>

                        {results.map((result, index) => (
                            <div
                                key={index}
                                className={`rounded-xl border p-4 ${
                                    "error" in result
                                        ? "border-red-200 bg-red-50"
                                        : statusStyles[
                                              result.status
                                          ] ||
                                          "border-slate-200 bg-slate-50"
                                }`}
                            >
                                {"error" in result ? (
                                    <div>
                                        <p className="text-sm font-semibold text-red-700">
                                            Extraction failed
                                        </p>

                                        <p className="mt-1 text-sm text-red-600">
                                            {result.error ||
                                                "Unknown error"}
                                        </p>

                                        {result.filename && (
                                            <p className="mt-1 text-xs text-red-500">
                                                {result.filename}
                                            </p>
                                        )}
                                    </div>
                                ) : (
                                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">

                                        <span className="text-sm font-semibold">
                                            {result.name ||
                                                "Unnamed candidate"}
                                        </span>

                                        <span
                                            className={`rounded-full border px-2 py-1 text-xs font-bold ${
                                                statusStyles[
                                                    result.status
                                                ] ||
                                                "border-slate-200 bg-slate-50 text-slate-600"
                                            }`}
                                        >
                                            {result.status.replace(
                                                "_",
                                                " "
                                            )}
                                        </span>

                                        <span className="text-xs text-slate-500">
                                            v{result.version}
                                        </span>

                                        <span className="text-xs text-slate-500">
                                            {
                                                result.experience_count_after_merge
                                            }{" "}
                                            experiences
                                        </span>
                                    </div>
                                )}
                            </div>
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ================================================== */}
            {/* SEARCH */}
            {/* ================================================== */}

            <div className="mt-6 flex items-center justify-between">

                <div className="relative w-full max-w-sm">

                    <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />

                    <input
                        value={query}
                        onChange={(e) =>
                            setQuery(e.target.value)
                        }
                        placeholder="Search candidates..."
                        className="field w-full pl-9"
                    />
                </div>

                <div className="flex items-center gap-3 text-sm text-slate-500">

                    <span>
                        {candidates.length} candidate(s)
                    </span>

                    <button
                        type="button"
                        onClick={() =>
                            loadCandidates(query)
                        }
                        className="hover:text-slate-800"
                        aria-label="Refresh"
                    >
                        <RefreshCw className="h-4 w-4" />
                    </button>

                </div>
            </div>

            {/* ================================================== */}
            {/* CANDIDATES LIST */}
            {/* ================================================== */}

            <div className="mt-4">

                {loading && candidates.length === 0 ? (

                    <div className="flex items-center justify-center py-10 text-slate-400">
                        <Loader2 className="h-6 w-6 animate-spin" />
                    </div>

                ) : candidates.length === 0 ? (

                    <p className="py-6 text-center text-sm text-slate-400">
                        No candidates found.
                    </p>

                ) : (

                    <AnimatePresence initial={false}>
                        <div className="grid gap-2">

                            {candidates.map((candidate) => (

                                <motion.div
                                    key={candidate.candidate_id}
                                    layout
                                    initial={{
                                        opacity: 0,
                                    }}
                                    animate={{
                                        opacity: 1,
                                    }}
                                    exit={{
                                        opacity: 0,
                                    }}
                                    className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3"
                                >

                                    {/* Candidate information */}

                                    <div className="min-w-0 flex-1">

                                        <p className="truncate text-sm font-semibold">
                                            {candidate.name}
                                        </p>

                                        {candidate.email && (
                                            <p className="truncate text-xs text-slate-500">
                                                {candidate.email}
                                            </p>
                                        )}

                                    </div>

                                    {/* View */}

                                    <button
                                        type="button"
                                        onClick={() =>
                                            onViewCandidate(
                                                candidate.candidate_id,
                                                candidate.name
                                            )
                                        }
                                        className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                                    >
                                        <Eye className="h-3.5 w-3.5" />

                                        View
                                    </button>

                                    {/* Delete */}

                                    <button
                                        type="button"
                                        onClick={() =>
                                            handleDelete(
                                                candidate.candidate_id,
                                                candidate.name
                                            )
                                        }
                                        disabled={
                                            deletingId ===
                                            candidate.candidate_id
                                        }
                                        className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 disabled:opacity-60"
                                    >
                                        {deletingId ===
                                        candidate.candidate_id ? (
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