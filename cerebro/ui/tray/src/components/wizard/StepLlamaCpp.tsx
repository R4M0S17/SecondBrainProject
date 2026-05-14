import { useEffect, useState } from "react";
import { wizardCheckLlamaCpp } from "../../api/client";

interface StepLlamaCppProps {
  onReady: (ready: boolean) => void;
}

export default function StepLlamaCpp({ onReady }: StepLlamaCppProps) {
  const [running, setRunning] = useState<boolean | null>(null);
  const [skippedReason, setSkippedReason] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const res = await wizardCheckLlamaCpp();
        if (!cancelled) {
          if (res.status === "skipped") {
            setRunning(true);
            setSkippedReason(res.reason ?? null);
            onReady(true);
          } else {
            setSkippedReason(null);
            setRunning(res.running);
            onReady(res.running);
          }
        }
      } catch {
        if (!cancelled) {
          setRunning(false);
          onReady(false);
        }
      }
    }

    check();
    const id = setInterval(check, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [onReady]);

  return (
    <div className="w-full space-y-4 mb-6">
      <p className="text-[14px] leading-[20px] text-[#e8eaf0] text-center leading-relaxed">
        {skippedReason
          ? "Inference is configured for Claude API — a local llama.cpp chat server is not required. Embeddings still use the local embed server when you index files."
          : "Cerebro needs the llama.cpp server running locally to index your private data and execute models on-device."}
      </p>

      {/* Status block */}
      <div className="bg-[#0f1117] rounded-lg p-[14px_16px] flex items-center justify-between border border-[#242736]/50">
        <div className="flex items-center gap-3">
          {running === null ? (
            <div className="w-2 h-2 rounded-full border-2 border-[#8b8fa8] border-t-transparent animate-spin" />
          ) : skippedReason ? (
            <div className="w-2 h-2 rounded-full bg-[#a78bfa]" />
          ) : running ? (
            <div className="w-2 h-2 rounded-full bg-[#4ade80] status-dot-pulse" />
          ) : (
            <div className="w-2 h-2 rounded-full bg-[#ffb4ab]" />
          )}
          <span
            className={`text-[14px] font-medium ${
              running === null
                ? "text-[#8b8fa8]"
                : skippedReason
                  ? "text-[#a78bfa]"
                  : running
                    ? "text-[#4ade80]"
                    : "text-[#ffb4ab]"
            }`}
          >
            {running === null
              ? "Checking llama.cpp server…"
              : skippedReason
                ? skippedReason
                : running
                  ? "llama.cpp server is running"
                  : "llama.cpp server not detected"}
          </span>
        </div>
        {running !== null && (
          <div
            className={`font-bold text-[10px] px-2 py-1 rounded uppercase tracking-wider ${
              skippedReason
                ? "bg-[#a78bfa]/15 text-[#a78bfa]"
                : running
                  ? "bg-[#4ade80]/15 text-[#4ade80]"
                  : "bg-[#ffb4ab]/15 text-[#ffb4ab]"
            }`}
          >
            {skippedReason ? "Skipped" : running ? "Detected" : "Not found"}
          </div>
        )}
      </div>

      {!skippedReason && !running && running !== null && (
        <p className="text-[12px] text-[#8b8fa8] text-center">
          Run{" "}
          <code className="text-[#94a3b8] bg-[#201f27] px-1 rounded">make engine</code>{" "}
          in a terminal, then wait for detection above.
        </p>
      )}
    </div>
  );
}
