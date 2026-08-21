// file: src/components/BackendStatusGate.tsx

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Loader2,
  Server,
  Database,
  BrainCircuit,
  WifiOff,
} from "lucide-react";

const POLL_INTERVAL_MS = 1500;
const REQUEST_TIMEOUT_MS = 5000;
const BASE = "/";

type Status = "starting" | "offline" | "ready";

const messages = [
  {
    text: "Loading embedding model",
    icon: BrainCircuit,
  },
  {
    text: "Initializing vector database",
    icon: Database,
  },
  {
    text: "Preparing AI services",
    icon: Server,
  },
];

export function BackendStatusGate({
  children,
}: {
  children: React.ReactNode;
}) {
  const [status, setStatus] = useState<Status>("starting");
  const [elapsed, setElapsed] = useState(0);
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed((v) => v + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      setMessageIndex((v) => (v + 1) % messages.length);
    }, 2500);

    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      const controller = new AbortController();

      const timeout = setTimeout(() => {
        controller.abort();
      }, REQUEST_TIMEOUT_MS);

      try {
        const res = await fetch(`${BASE}health`, {
          cache: "no-store",
          signal: controller.signal,
        });

        clearTimeout(timeout);

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }

        const data = await res.json();

        if (cancelled) return;

        if (data.ready === true) {
          setStatus("ready");
          return;
        }

        setStatus("starting");
      } catch {
        if (cancelled) return;

        setStatus("offline");
      }

      if (!cancelled) {
        pollTimer = setTimeout(poll, POLL_INTERVAL_MS);
      }
    };

    poll();

    return () => {
      cancelled = true;
      clearTimeout(pollTimer);
    };
  }, []);

  if (status === "ready") {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.35 }}
      >
        {children}
      </motion.div>
    );
  }

  const CurrentIcon = messages[messageIndex].icon;

  return (
    <AnimatePresence>
      <motion.div
        key="loading-screen"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[999] overflow-hidden bg-gradient-to-br from-slate-50 via-white to-slate-100"
      >
        {/* Background blobs */}
        <div className="absolute inset-0 overflow-hidden">
          <motion.div
            className="absolute -left-32 top-20 h-80 w-80 rounded-full bg-red-100 blur-3xl"
            animate={{
              x: [0, 40, 0],
              y: [0, 20, 0],
            }}
            transition={{
              duration: 8,
              repeat: Infinity,
            }}
          />

          <motion.div
            className="absolute -right-32 bottom-20 h-80 w-80 rounded-full bg-slate-200 blur-3xl"
            animate={{
              x: [0, -40, 0],
              y: [0, -20, 0],
            }}
            transition={{
              duration: 10,
              repeat: Infinity,
            }}
          />
        </div>

        <div className="relative flex min-h-screen items-center justify-center p-6">
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="w-full max-w-md rounded-3xl border border-slate-200 bg-white/80 p-8 shadow-2xl backdrop-blur-xl"
          >
            <div className="flex flex-col items-center">
              {/* Logo spinner */}
              <div className="relative mb-6">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{
                    repeat: Infinity,
                    duration: 1.5,
                    ease: "linear",
                  }}
                >
                  <Loader2 className="h-12 w-12 text-[#C1121F]" />
                </motion.div>

                <motion.div
                  className="absolute inset-0 rounded-full border-4 border-red-100"
                  animate={{
                    scale: [1, 1.15, 1],
                    opacity: [0.5, 0.2, 0.5],
                  }}
                  transition={{
                    duration: 2,
                    repeat: Infinity,
                  }}
                />
              </div>

              <h2 className="text-xl font-bold text-slate-900">
                CV Platform
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                Backend initialization
              </p>

              {/* Status Card */}
              <div className="mt-8 w-full rounded-2xl bg-slate-50 p-4">
                <div className="flex items-center gap-3">
                  {status === "offline" ? (
                    <WifiOff className="h-5 w-5 text-red-500" />
                  ) : (
                    <CurrentIcon className="h-5 w-5 text-[#C1121F]" />
                  )}

                  <span className="text-sm font-medium text-slate-700">
                    {status === "offline"
                      ? "Waiting for backend connection..."
                      : messages[messageIndex].text}
                  </span>
                </div>

                {/* Animated Progress */}
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-200">
                  <motion.div
                    className="h-full w-1/3 rounded-full bg-[#C1121F]"
                    animate={{
                      x: ["-100%", "350%"],
                    }}
                    transition={{
                      duration: 1.8,
                      repeat: Infinity,
                      ease: "linear",
                    }}
                  />
                </div>
              </div>

              {/* Elapsed time */}
              <div className="mt-5 text-center">
                <p className="text-xs font-medium text-slate-600">
                  Startup time
                </p>

                <motion.p
                  key={elapsed}
                  initial={{ opacity: 0.5 }}
                  animate={{ opacity: 1 }}
                  className="mt-1 text-lg font-bold text-slate-900"
                >
                  {elapsed}s
                </motion.p>
              </div>

              {/* Tips */}
              <p className="mt-6 text-center text-xs leading-relaxed text-slate-500">
                The AI engine is loading embeddings, vector indexes and search
                services. This may take a few moments.
              </p>
            </div>
          </motion.div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}