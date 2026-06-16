import { useState, useCallback } from "react";
import ServiceControls from "../components/status/ServiceControls";
import WorkflowPanel from "../components/automation/WorkflowPanel";
import { triggerSync } from "../api/client";

interface Toast {
  message: string;
  type: "success" | "error";
}

interface HeaderProps {
  onDocumentsOpen?: () => void;
  onSettingsOpen?: () => void;
  onDebugOpen?: () => void;
}

export default function Header({ onDocumentsOpen, onSettingsOpen, onDebugOpen }: HeaderProps) {
  const [workflowsOpen, setWorkflowsOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);

  const showToast = useCallback((message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  }, []);

  const handleSync = useCallback(async () => {
    setSyncing(true);
    try {
      const res = await triggerSync({ force: true });
      if (res.status === "processing") {
        showToast("Sync started", "success");
        // Notify SourcesView to refresh after a brief delay for backend processing
        setTimeout(() => {
          window.dispatchEvent(new CustomEvent("knowledge-sync-complete"));
        }, 3000);
      } else {
        showToast(`Sync: ${res.status}`, "error");
      }
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Sync failed", "error");
    } finally {
      setSyncing(false);
    }
  }, [showToast]);

  return (
    <header
      data-tauri-drag-region
      className="flex justify-between items-center w-full px-4 md:px-margin-desktop h-12 bg-background/80 backdrop-blur-md border-b border-outline-variant/30 z-50 shrink-0"
      role="banner"
    >
      <div className="flex items-center gap-4" data-tauri-drag-region>
        <img src="/BestLogo.svg" alt="Cerebro" className="h-7 w-7 object-contain shrink-0" />
        <span className="text-sm font-bold text-on-surface select-none">
          Cerebro
        </span>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <div className="hidden md:flex gap-1">
          <ServiceControls />
        </div>
        <div className="flex items-center gap-1 text-on-surface-variant">
          <button
            onClick={onDocumentsOpen}
            className="p-1.5 hover:text-primary transition-colors rounded hover:bg-surface-container"
            aria-label="Documents"
            title="Documents"
          >
            <span className="material-symbols-outlined text-[18px]">description</span>
          </button>
          <button
            onClick={() => void handleSync()}
            disabled={syncing}
            className="p-1.5 hover:text-primary transition-colors rounded hover:bg-surface-container disabled:opacity-50"
            aria-label="Sync all sources"
            title="Sync all sources"
          >
            {syncing ? (
              <span className="inline-block w-[18px] h-[18px] border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <span className="material-symbols-outlined text-[18px]">sync</span>
            )}
          </button>
          <button
            onClick={onSettingsOpen}
            className="p-1.5 hover:text-primary transition-colors rounded hover:bg-surface-container"
            aria-label="Settings"
            title="Settings (⌘,)"
          >
            <span className="material-symbols-outlined text-[18px]">settings</span>
          </button>
          <button
            onClick={onDebugOpen}
            className="p-1.5 hover:text-primary transition-colors rounded hover:bg-surface-container"
            aria-label="History/Debug"
            title="Time-Travel Debugger"
          >
            <span className="material-symbols-outlined text-[18px]">history</span>
          </button>
          <button
            onClick={() => setWorkflowsOpen(true)}
            className="p-1.5 hover:text-primary transition-colors rounded hover:bg-surface-container"
            aria-label="Monitoring"
            title="Desktop Workflows"
          >
            <span className="material-symbols-outlined text-[18px]">monitoring</span>
          </button>
        </div>
      </div>

      {workflowsOpen && <WorkflowPanel onClose={() => setWorkflowsOpen(false)} />}

      {toast && (
        <div
          className={`fixed bottom-4 right-4 z-[100] px-4 py-2.5 rounded-[8px] text-[13px] font-semibold shadow-lg transition-all duration-300 ${
            toast.type === "success"
              ? "bg-success-green/90 text-white"
              : "bg-error/90 text-white"
          }`}
        >
          <div className="flex items-center gap-2">
            {toast.type === "success" ? (
              <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                <path d="M20 6L9 17l-5-5" />
              </svg>
            ) : (
              <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4M12 16h.01" />
              </svg>
            )}
            {toast.message}
            <button onClick={() => setToast(null)} className="ml-2 opacity-70 hover:opacity-100">
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </header>
  );
}
