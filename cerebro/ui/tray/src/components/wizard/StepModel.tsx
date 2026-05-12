import { useCallback, useEffect, useState } from "react";
import { getLlamaCppModels, wizardCheckModels } from "../../api/client";
import type { LlamaCppModel } from "../../api/types";

interface StepModelProps {
  onReady: (ready: boolean) => void;
}

type CheckState = "checking" | "ok" | "missing" | "error";

export default function StepModel({ onReady }: StepModelProps) {
  const [state, setState] = useState<CheckState>("checking");
  const [message, setMessage] = useState<string>("");
  const [models, setModels] = useState<LlamaCppModel[]>([]);

  const check = useCallback(async () => {
    setState("checking");
    onReady(false);
    try {
      const [{ ok, message: msg }, { models: found }] = await Promise.all([
        wizardCheckModels(),
        getLlamaCppModels(),
      ]);
      setMessage(msg);
      setModels(found);
      if (ok) {
        setState("ok");
        onReady(true);
      } else {
        setState("missing");
      }
    } catch (e) {
      setState("error");
      setMessage((e as Error).message ?? "Check failed");
    }
  }, [onReady]);

  useEffect(() => {
    check();
  }, [check]);

  return (
    <div className="w-full space-y-3 mb-6">
      <p className="text-[14px] text-[#e8eaf0] text-center mb-4">
        Verifying GGUF model files in{" "}
        <code className="text-[#94a3b8] bg-[#201f27] px-1 rounded">bin/models/</code>.
      </p>

      {/* Status block */}
      <div
        className={`rounded-lg border p-[14px_16px] transition-colors ${
          state === "ok"
            ? "border-[#4ade80]/40 bg-[#4ade80]/5"
            : state === "missing" || state === "error"
            ? "border-[#ffb4ab]/40 bg-[#ffb4ab]/5"
            : "border-[#242736]/50 bg-[#0f1117]"
        }`}
      >
        <div className="flex items-center gap-3">
          {state === "checking" ? (
            <div className="w-2 h-2 rounded-full border-2 border-[#8b8fa8] border-t-transparent animate-spin shrink-0" />
          ) : state === "ok" ? (
            <div className="w-2 h-2 rounded-full bg-[#4ade80] shrink-0" />
          ) : (
            <div className="w-2 h-2 rounded-full bg-[#ffb4ab] shrink-0" />
          )}
          <span
            className={`text-[14px] font-medium ${
              state === "checking"
                ? "text-[#8b8fa8]"
                : state === "ok"
                ? "text-[#4ade80]"
                : "text-[#ffb4ab]"
            }`}
          >
            {state === "checking"
              ? "Scanning model files…"
              : state === "ok"
              ? `${models.length} model${models.length !== 1 ? "s" : ""} found`
              : message || "No models found"}
          </span>
        </div>

        {state === "ok" && models.length > 0 && (
          <ul className="mt-3 space-y-1">
            {models.map((m) => (
              <li key={m.name} className="flex items-center justify-between text-[12px]">
                <span className="font-mono text-[#e8eaf0]">{m.name}</span>
                <span className="text-[#8b8fa8]">{m.size_gb.toFixed(1)} GB</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {(state === "missing" || state === "error") && (
        <>
          <p className="text-[12px] text-[#8b8fa8] text-center">
            Place GGUF files in{" "}
            <code className="text-[#94a3b8] bg-[#201f27] px-1 rounded">bin/models/</code>
            , then click Retry.
          </p>
          <div className="flex justify-center">
            <button
              onClick={check}
              className="px-4 py-1.5 text-[12px] bg-primary text-[#0f1117] rounded hover:opacity-90 transition-opacity font-semibold"
            >
              Retry
            </button>
          </div>
        </>
      )}
    </div>
  );
}
