import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import ServiceControls from "../components/status/ServiceControls";
import { triggerSync } from "../api/client";
import Toast from "../components/shared/Toast";

interface HeaderProps {
  onDocumentsOpen?: () => void;
  onMemoryBrowserOpen?: () => void;
  onWorkflowsOpen?: () => void;
  onSettingsOpen?: () => void;
  onDebugOpen?: () => void;
}

export default function Header({ onDocumentsOpen, onMemoryBrowserOpen, onWorkflowsOpen, onSettingsOpen, onDebugOpen }: HeaderProps) {
  const { t } = useTranslation();
  const [syncing, setSyncing] = useState(false);
  const [toastState, setToastState] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const showToast = useCallback((message: string, type: "success" | "error") => {
    setToastState({ message, type });
  }, []);

  const dismissToast = useCallback(() => setToastState(null), []);

  const handleSync = useCallback(async () => {
    setSyncing(true);
    try {
      const res = await triggerSync({ force: true });
      if (res.status === "processing") {
        showToast(t("sync.started"), "success");
        setTimeout(() => {
          window.dispatchEvent(new CustomEvent("knowledge-sync-complete"));
        }, 3000);
      } else {
        showToast(`Sync: ${res.status}`, "error");
      }
    } catch (e) {
      showToast(e instanceof Error ? e.message : t("sync.failed"), "error");
    } finally {
      setSyncing(false);
    }
  }, [showToast, t]);

  return (
    <header
      data-tauri-drag-region
      className="flex justify-between items-center w-full pl-3 pr-4 md:pl-5 md:pr-margin-desktop h-12 bg-background/80 backdrop-blur-md border-b border-outline-variant/30 z-50 shrink-0"
      role="banner"
    >
      <div className="flex items-center gap-2.5" data-tauri-drag-region>
        <img src="/BestLogo.svg" alt="Cerebro" className="h-7 w-7 object-contain shrink-0" />
        <span className="text-sm font-bold text-on-surface select-none">
          Cerebro
        </span>
      </div>

      <div className="flex items-center shrink-0">
        {/* Primary actions */}
        <div className="flex items-center gap-0.5 text-on-surface-variant">
          <button
            onClick={() => void handleSync()}
            disabled={syncing}
            className="p-1.5 hover:text-primary transition-colors rounded-lg hover:bg-surface-container disabled:opacity-50"
            aria-label={t("header.sync")}
            title={t("header.sync")}
          >
            {syncing ? (
              <span className="inline-block w-[18px] h-[18px] border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <span className="material-symbols-outlined text-[18px]">sync</span>
            )}
          </button>
          <button
            onClick={onDocumentsOpen}
            className="p-1.5 hover:text-primary transition-colors rounded-lg hover:bg-surface-container"
            aria-label={t("header.documents")}
            title={t("header.documents")}
          >
            <span className="material-symbols-outlined text-[18px]">description</span>
          </button>
          <button
            onClick={onMemoryBrowserOpen}
            className="p-1.5 hover:text-primary transition-colors rounded-lg hover:bg-surface-container"
            aria-label={t("header.memories")}
            title={t("header.memories")}
          >
            <span className="material-symbols-outlined text-[18px]">psychology</span>
          </button>
          <button
            onClick={onWorkflowsOpen}
            className="p-1.5 hover:text-primary transition-colors rounded-lg hover:bg-surface-container"
            aria-label={t("header.workflows")}
            title={t("header.workflows")}
          >
            <span className="material-symbols-outlined text-[18px]">account_tree</span>
          </button>
        </div>

        <div className="w-px h-4 bg-outline-variant/20 mx-1.5" />

        {/* Configuration */}
        <div className="flex items-center gap-0.5 text-on-surface-variant">
          <button
            onClick={onSettingsOpen}
            className="p-1.5 hover:text-primary transition-colors rounded-lg hover:bg-surface-container"
            aria-label={t("header.settings")}
            title={t("header.settings")}
          >
            <span className="material-symbols-outlined text-[18px]">settings</span>
          </button>
        </div>

        <div className="w-px h-4 bg-outline-variant/20 mx-1.5" />

        {/* Advanced */}
        <div className="flex items-center gap-0.5 text-on-surface-variant">
          <button
            onClick={onDebugOpen}
            className="p-1.5 hover:text-primary transition-colors rounded-lg hover:bg-surface-container"
            aria-label={t("header.debug")}
            title={t("header.time_travel_debugger")}
          >
            <span className="material-symbols-outlined text-[18px]">history</span>
          </button>
        </div>

        <div className="w-px h-4 bg-outline-variant/20 mx-1.5" />

        {/* Service */}
        <div className="hidden md:flex items-center gap-0.5">
          <ServiceControls />
        </div>
      </div>

      <Toast
        visible={toastState !== null}
        onDismiss={dismissToast}
        duration={4000}
        className={`fixed bottom-4 right-4 z-[100] ${
          toastState?.type === "success"
            ? "bg-success-green/90 text-white"
            : "bg-error/90 text-white"
        }`}
      >
        {toastState?.type === "success" ? (
          <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
            <path d="M20 6L9 17l-5-5" />
          </svg>
        ) : (
          <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" />
          </svg>
        )}
        {toastState?.message}
      </Toast>
    </header>
  );
}
