import { useEffect, useState, useCallback, useRef } from "react";
import { useWorkflowStore } from "../../stores/workflows";

// ─── Standalone overlay window (Tauri secondary window) ──────────────────────
// When rendered inside the recording-overlay window, it talks back to the
// main window via Tauri events instead of calling the store directly.

async function isTauriOverlayWindow(): Promise<boolean> {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    return getCurrentWindow().label === "recording-overlay";
  } catch {
    return false;
  }
}

async function emitStop() {
  try {
    const { emit } = await import("@tauri-apps/api/event");
    await emit("recording-overlay:stop");
  } catch { /* dev browser — store handles it via in-app overlay */ }
}

// ─── In-app overlay (rendered inside MainLayout for dev mode + Tauri) ────────

export default function RecordingOverlay() {
  const isRecording = useWorkflowStore((s) => s.isRecording);
  const stopRecording = useWorkflowStore((s) => s.stopRecording);
  const cancelRecording = useWorkflowStore((s) => s.cancelRecording);

  const [paused, setPaused] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startedAtRef = useRef<number>(Date.now());
  const accumulatedRef = useRef<number>(0);

  // Reset on new recording session
  useEffect(() => {
    if (isRecording) {
      setPaused(false);
      setElapsed(0);
      startedAtRef.current = Date.now();
      accumulatedRef.current = 0;
    }
  }, [isRecording]);

  // Timer
  useEffect(() => {
    if (!isRecording || paused) return;
    const id = setInterval(() => {
      setElapsed(
        accumulatedRef.current + Math.floor((Date.now() - startedAtRef.current) / 1000)
      );
    }, 500);
    return () => clearInterval(id);
  }, [isRecording, paused]);

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60).toString().padStart(2, "0");
    const sec = (s % 60).toString().padStart(2, "0");
    return `${m}:${sec}`;
  };

  const handlePause = useCallback(() => {
    if (!paused) {
      accumulatedRef.current += Math.floor((Date.now() - startedAtRef.current) / 1000);
      setPaused(true);
    } else {
      startedAtRef.current = Date.now();
      setPaused(false);
    }
  }, [paused]);

  const handleStop = useCallback(() => {
    void stopRecording();
  }, [stopRecording]);

  const handleCancel = useCallback(() => {
    void cancelRecording();
  }, [cancelRecording]);

  if (!isRecording) return null;

  return (
    <div
      className="
        fixed top-4 right-4 z-[9999]
        flex items-center gap-2 px-3 py-2
        bg-[#1c1c1e]/95 backdrop-blur-xl
        rounded-2xl border border-white/10
        shadow-[0_4px_24px_rgba(0,0,0,0.5)]
        select-none
      "
      style={{ minWidth: 200 }}
    >
      {/* Dot */}
      <div className="relative flex-shrink-0 w-2.5 h-2.5">
        <div className={`w-2.5 h-2.5 rounded-full ${paused ? "bg-yellow-400" : "bg-red-500"}`} />
        {!paused && (
          <div className="absolute inset-0 rounded-full bg-red-500 animate-ping opacity-70" />
        )}
      </div>

      {/* Label + timer */}
      <div className="flex flex-col leading-none flex-1">
        <span className="text-white/50 text-[10px] uppercase tracking-wider">
          {paused ? "Pausado" : "Grabando"}
        </span>
        <span className="text-white text-[13px] font-mono font-medium mt-0.5">
          {formatTime(elapsed)}
        </span>
      </div>

      {/* Pause */}
      <button
        onClick={handlePause}
        title={paused ? "Reanudar" : "Pausar"}
        className="w-7 h-7 rounded-lg flex items-center justify-center text-[13px] bg-white/10 hover:bg-white/20 text-white transition-colors"
      >
        {paused ? "▶" : "⏸"}
      </button>

      {/* Stop & save */}
      <button
        onClick={handleStop}
        title="Detener y guardar"
        className="w-7 h-7 rounded-lg flex items-center justify-center text-[12px] font-bold bg-red-500/80 hover:bg-red-500 text-white transition-colors"
      >
        ■
      </button>

      {/* Cancel */}
      <button
        onClick={handleCancel}
        title="Cancelar y descartar"
        className="w-7 h-7 rounded-lg flex items-center justify-center text-[13px] bg-white/8 hover:bg-white/15 text-white/50 hover:text-white transition-colors"
      >
        ✕
      </button>
    </div>
  );
}

// ─── Standalone version for the recording-overlay Tauri window ───────────────

export function StandaloneRecordingOverlay() {
  const [paused, setPaused] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startedAtRef = useRef<number>(Date.now());
  const accumulatedRef = useRef<number>(0);

  useEffect(() => {
    if (paused) return;
    const id = setInterval(() => {
      setElapsed(
        accumulatedRef.current + Math.floor((Date.now() - startedAtRef.current) / 1000)
      );
    }, 500);
    return () => clearInterval(id);
  }, [paused]);

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60).toString().padStart(2, "0");
    const sec = (s % 60).toString().padStart(2, "0");
    return `${m}:${sec}`;
  };

  const handlePause = useCallback(async () => {
    if (!paused) {
      accumulatedRef.current += Math.floor((Date.now() - startedAtRef.current) / 1000);
      setPaused(true);
      try {
        const { emit } = await import("@tauri-apps/api/event");
        await emit("recording-overlay:pause");
      } catch { /* ignore */ }
    } else {
      startedAtRef.current = Date.now();
      setPaused(false);
      try {
        const { emit } = await import("@tauri-apps/api/event");
        await emit("recording-overlay:resume");
      } catch { /* ignore */ }
    }
  }, [paused]);

  const handleStop = useCallback(async () => {
    await emitStop();
  }, []);

  const handleCancel = useCallback(async () => {
    try {
      const { emit } = await import("@tauri-apps/api/event");
      await emit("recording-overlay:cancel");
    } catch { /* ignore */ }
  }, []);

  return (
    <div
      className="
        w-full h-full flex items-center gap-2 px-3
        bg-[#1c1c1e]/95 backdrop-blur-xl
        rounded-2xl border border-white/10
        shadow-[0_4px_24px_rgba(0,0,0,0.6)]
        select-none
      "
      style={{ WebkitAppRegion: "drag" } as React.CSSProperties}
    >
      {/* Dot */}
      <div className="relative flex-shrink-0 w-2.5 h-2.5">
        <div className={`w-2.5 h-2.5 rounded-full ${paused ? "bg-yellow-400" : "bg-red-500"}`} />
        {!paused && (
          <div className="absolute inset-0 rounded-full bg-red-500 animate-ping opacity-70" />
        )}
      </div>

      {/* Timer */}
      <div className="flex flex-col leading-none flex-1">
        <span className="text-white/50 text-[10px] uppercase tracking-wider">
          {paused ? "Pausado" : "Grabando"}
        </span>
        <span className="text-white text-[13px] font-mono font-medium mt-0.5">
          {formatTime(elapsed)}
        </span>
      </div>

      {/* Pause */}
      <button
        style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
        onClick={handlePause}
        title={paused ? "Reanudar" : "Pausar"}
        className="w-7 h-7 rounded-lg flex items-center justify-center text-[13px] bg-white/10 hover:bg-white/20 text-white transition-colors"
      >
        {paused ? "▶" : "⏸"}
      </button>

      {/* Stop */}
      <button
        style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
        onClick={handleStop}
        title="Detener y guardar"
        className="w-7 h-7 rounded-lg flex items-center justify-center text-[12px] font-bold bg-red-500/80 hover:bg-red-500 text-white transition-colors"
      >
        ■
      </button>

      {/* Cancel */}
      <button
        style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
        onClick={handleCancel}
        title="Cancelar y descartar"
        className="w-7 h-7 rounded-lg flex items-center justify-center text-[13px] bg-white/8 hover:bg-white/15 text-white/50 hover:text-white transition-colors"
      >
        ✕
      </button>
    </div>
  );
}
