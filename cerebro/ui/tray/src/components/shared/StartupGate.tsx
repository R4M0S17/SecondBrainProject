import { useCallback, useEffect, useState, type ReactNode } from "react";
import { invoke } from "@tauri-apps/api/core";
import { getHealth } from "../../api/client";
import { isTauriRuntime } from "../../lib/tauri";

const POLL_MS = 1000;
const TIMEOUT_MS = 130_000;
const LOG_HINT = "~/.cerebro/logs/";

type Phase = "starting" | "ready" | "error";

interface StartupGateProps {
  children: ReactNode;
}

export default function StartupGate({ children }: StartupGateProps) {
  const [phase, setPhase] = useState<Phase>(isTauriRuntime() ? "starting" : "ready");
  const [detail, setDetail] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  const checkHealth = useCallback(async (): Promise<boolean> => {
    try {
      await getHealth();
      return true;
    } catch {
      return false;
    }
  }, []);

  useEffect(() => {
    if (!isTauriRuntime()) {
      return;
    }

    let cancelled = false;
    const startedAt = Date.now();

    const tick = async () => {
      if (cancelled) {
        return;
      }
      const ok = await checkHealth();
      if (cancelled) {
        return;
      }
      if (ok) {
        setPhase("ready");
        setDetail(null);
        return;
      }
      if (Date.now() - startedAt >= TIMEOUT_MS) {
        setPhase("error");
        setDetail(
          `Backend did not respond within ${TIMEOUT_MS / 1000}s. Check ${LOG_HINT} or run: make desktop-launch`
        );
      }
    };

    void tick();
    const id = window.setInterval(() => void tick(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [checkHealth]);

  const onRetry = async () => {
    setRetrying(true);
    setPhase("starting");
    setDetail(null);
    try {
      if (isTauriRuntime()) {
        await invoke("restart_cerebro_services");
      }
      const ok = await checkHealth();
      if (!ok) {
        setPhase("error");
        setDetail(`Services still unavailable. See ${LOG_HINT}`);
      } else {
        setPhase("ready");
      }
    } catch (err) {
      setPhase("error");
      setDetail(err instanceof Error ? err.message : String(err));
    } finally {
      setRetrying(false);
    }
  };

  if (phase === "ready") {
    return <>{children}</>;
  }

  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[400px] bg-[#0f1117] text-[#e5e0ed] gap-4 p-8">
      {phase === "starting" ? (
        <>
          <div
            className="h-8 w-8 rounded-full border-2 border-[#8b8fa8] border-t-[#e5e0ed] animate-spin"
            aria-hidden
          />
          <p className="text-[16px] font-semibold">Starting Cerebro…</p>
          <p className="text-[12px] text-[#8b8fa8] text-center max-w-sm">
            Launching the local engine and API. First start can take 1–3 minutes.
          </p>
        </>
      ) : (
        <>
          <p className="text-[16px] font-semibold">Could not start Cerebro</p>
          <p className="text-[12px] text-[#8b8fa8] text-center max-w-sm">
            {detail ?? `Check logs in ${LOG_HINT}`}
          </p>
          <button
            type="button"
            disabled={retrying}
            onClick={() => void onRetry()}
            className="px-4 py-2 bg-[#94a3b8] text-[#0f1117] rounded text-[14px] font-semibold disabled:opacity-50"
          >
            {retrying ? "Retrying…" : "Retry"}
          </button>
          <p className="text-[11px] text-[#8b8fa8]">
            Or run <code className="text-[#c9c4d7]">make desktop-launch</code> in Terminal
          </p>
        </>
      )}
    </div>
  );
}
