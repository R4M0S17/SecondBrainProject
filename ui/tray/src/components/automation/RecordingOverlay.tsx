import { useEffect, useState, useCallback, useRef } from "react";
import { useWorkflowStore } from "../../stores/workflows";

// ─── Iconos SVG para botones ─────────────────────────────────────────────────

function PlayIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

function PauseIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
    </svg>
  );
}

function StopIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M6 6h12v12H6z" />
    </svg>
  );
}

function CloseIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
    </svg>
  );
}

// ─── In-app overlay (dev mode / browser fallback) ────────────────────────────

export default function RecordingOverlay() {
  const isRecording = useWorkflowStore((s) => s.isRecording);
  const hasNativeOverlay = useWorkflowStore((s) => s.hasNativeOverlay);
  const stopRecording = useWorkflowStore((s) => s.stopRecording);
  const cancelRecording = useWorkflowStore((s) => s.cancelRecording);

  const [paused, setPaused] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startedAtRef = useRef<number>(Date.now());
  const accumulatedRef = useRef<number>(0);

  useEffect(() => {
    if (isRecording) {
      setPaused(false);
      setElapsed(0);
      startedAtRef.current = Date.now();
      accumulatedRef.current = 0;
    }
  }, [isRecording]);

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

  const handleStop = useCallback(() => { void stopRecording(); }, [stopRecording]);
  const handleCancel = useCallback(() => { void cancelRecording(); }, [cancelRecording]);

  // Hidden when the native Tauri overlay window is active to avoid duplicates
  if (!isRecording || hasNativeOverlay) return null;

  return (
    <div
      className="fixed top-4 right-4 z-[9999] flex items-center gap-2 px-3 py-2
        bg-gradient-to-br from-[#1a1a1f]/95 to-[#0f0f13]/95
        backdrop-blur-xl rounded-2xl
        border border-white/[0.08]
        shadow-[0_8px_40px_rgba(0,0,0,0.7),inset_0_1px_0_rgba(255,255,255,0.05)]
        overflow-hidden select-none"
      style={{ minWidth: 200 }}
    >
      <RecDot paused={paused} />
      <RecLabel paused={paused} elapsed={elapsed} fmt={formatTime} />
      <OverlayButton onClick={handlePause} title={paused ? "Reanudar" : "Pausar"} variant="default">
        {paused ? <PlayIcon /> : <PauseIcon />}
      </OverlayButton>
      <OverlayButton onClick={handleStop} title="Detener y guardar" variant="stop">
        <StopIcon />
      </OverlayButton>
      <OverlayButton onClick={handleCancel} title="Cancelar y descartar" variant="cancel">
        <CloseIcon />
      </OverlayButton>
    </div>
  );
}

// ─── Standalone overlay — rendered inside the Tauri "recording-overlay" window ─
// Buttons call Rust commands directly (invoke) to avoid cross-window JS event
// routing issues in Tauri v2. Dragging uses startDragging() API (more reliable
// than -webkit-app-region: drag on transparent borderless windows on macOS).

export function StandaloneRecordingOverlay() {
  const [paused, setPaused] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startedAtRef = useRef<number>(Date.now());
  const accumulatedRef = useRef<number>(0);

  // Pre-cache the Tauri window reference so mousedown drag is synchronous
  const winRef = useRef<{ startDragging: () => Promise<void> } | null>(null);
  useEffect(() => {
    import("@tauri-apps/api/window")
      .then(({ getCurrentWindow }) => { winRef.current = getCurrentWindow(); })
      .catch(() => {});
  }, []);

  // Reset the timer when the overlay is shown — the window is persistent (hidden
  // at app launch) so Date.now() refs are stale from boot, not recording start.
  useEffect(() => {
    let unlisten: (() => void) | null = null;
    import("@tauri-apps/api/event")
      .then(({ listen }) => listen("recording-overlay:shown", () => {
        startedAtRef.current = Date.now();
        accumulatedRef.current = 0;
        setElapsed(0);
        setPaused(false);
      }))
      .then((fn) => { unlisten = fn; })
      .catch(() => {});
    return () => { unlisten?.(); };
  }, []);

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

  // Drag: only when NOT clicking a button
  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if ((e.target as Element).closest("button")) return;
    winRef.current?.startDragging().catch(() => {});
  }, []);

  const handlePause = useCallback(() => {
    if (!paused) {
      accumulatedRef.current += Math.floor((Date.now() - startedAtRef.current) / 1000);
      setPaused(true);
    } else {
      startedAtRef.current = Date.now();
      setPaused(false);
    }
  }, [paused]);

  // Stop/cancel invoke Rust commands that: hide overlay, emit event to main
  // window's JS listener via app.emit() (Rust-level, crosses windows reliably).
  const handleStop = useCallback(async () => {
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("overlay_stop_recording");
    } catch { /* not in Tauri */ }
  }, []);

  const handleCancel = useCallback(async () => {
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("overlay_cancel_recording");
    } catch { /* not in Tauri */ }
  }, []);

  return (
    <div
      onMouseDown={handleMouseDown}
      className="w-full h-full flex items-center gap-2 px-3 py-2
        bg-gradient-to-br from-[#1a1a1f]/95 to-[#0f0f13]/95
        backdrop-blur-xl rounded-2xl
        border border-white/[0.08]
        shadow-[0_8px_40px_rgba(0,0,0,0.7),inset_0_1px_0_rgba(255,255,255,0.05)]
        overflow-hidden select-none cursor-move"
    >
      <RecDot paused={paused} />
      <RecLabel paused={paused} elapsed={elapsed} fmt={formatTime} />
      <OverlayButton onClick={handlePause} title={paused ? "Reanudar" : "Pausar"} variant="default">
        {paused ? <PlayIcon /> : <PauseIcon />}
      </OverlayButton>
      <OverlayButton onClick={handleStop} title="Detener y guardar" variant="stop">
        <StopIcon />
      </OverlayButton>
      <OverlayButton onClick={handleCancel} title="Cancelar y descartar" variant="cancel">
        <CloseIcon />
      </OverlayButton>
    </div>
  );
}

// ─── Shared primitives ────────────────────────────────────────────────────────

function RecDot({ paused }: { paused: boolean }) {
  return (
    <div className="relative flex-shrink-0 w-3 h-3">
      <div
        className={`w-3 h-3 rounded-full transition-colors duration-300 ${
          paused ? "bg-yellow-400" : "bg-red-500"
        }`}
      />
      {!paused && (
        <div className="absolute inset-0 rounded-full bg-red-500 animate-ping opacity-75" />
      )}
    </div>
  );
}

function RecLabel({ paused, elapsed, fmt }: { paused: boolean; elapsed: number; fmt: (s: number) => string }) {
  return (
    <div className="flex flex-col leading-none flex-1 min-w-0">
      <span className="text-white/40 text-[10px] uppercase tracking-wider font-medium">
        {paused ? "Pausado" : "Grabando"}
      </span>
      <span className="text-white text-[15px] font-mono font-semibold mt-0.5 tabular-nums">
        {fmt(elapsed)}
      </span>
    </div>
  );
}

function OverlayButton({
  onClick,
  title,
  variant = "default",
  children,
}: {
  onClick: (() => void) | (() => Promise<void>);
  title: string;
  variant?: "default" | "stop" | "cancel";
  children: React.ReactNode;
}) {
  const baseClasses = "w-7 h-7 flex-shrink-0 rounded-lg flex items-center justify-center transition-all duration-200 cursor-pointer active:scale-90";

  const variantClasses = {
    default: "bg-white/[0.08] hover:bg-white/[0.15] text-white/70 hover:text-white hover:shadow-lg",
    stop: "bg-red-500/20 hover:bg-red-500/30 text-red-400 hover:text-red-300 hover:shadow-red-500/20 hover:shadow-lg",
    cancel: "bg-white/[0.05] hover:bg-white/[0.1] text-white/40 hover:text-white/70 hover:shadow-lg",
  };

  return (
    <button
      onClick={onClick}
      title={title}
      className={`${baseClasses} ${variantClasses[variant]}`}
    >
      {children}
    </button>
  );
}
