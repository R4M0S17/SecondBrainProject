import { useEffect, useState } from "react";
import { useSettingsStore } from "../../stores/settings";
import { useSystemStore, selectIsClaudeMode } from "../../stores/system";
import { switchInferenceBackend } from "../../api/client";
import FolderManager from "./FolderManager";
import IndexProgress from "./IndexProgress";
import ModelSelector from "./ModelSelector";
import ToolPermissions from "./ToolPermissions";
import DndToggle from "./DndToggle";
import FleetSettings from "./FleetSettings";

export default function SettingsPanel() {
  const { close, isOpen } = useSettingsStore();
  const status = useSystemStore((s) => s.status);
  const isCloud = selectIsClaudeMode(status);
  const [switching, setSwitching] = useState(false);

  const handleBackendSwitch = async (backend: "llamacpp" | "claude") => {
    setSwitching(true);
    try {
      await switchInferenceBackend(backend);
    } finally {
      setSwitching(false);
    }
  };

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [close]);

  return (
    <div className="absolute inset-0 z-40 flex" role="complementary" aria-label="Settings">
      {/* Backdrop */}
      <div
        className="flex-1 bg-black/40"
        onClick={close}
        aria-hidden="true"
      />

      {/* Slide-over panel — 320px from right */}
      <aside
        className={`w-[320px] h-full bg-[#1a1d27] border-l border-[#242736] flex flex-col z-10 transition-transform duration-200 ease-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <header className="h-[48px] flex items-center justify-between px-4 bg-[#1a1d27] border-b border-[#242736] shrink-0">
          <h2 className="text-[15px] font-semibold text-[#e5e0ed]">Settings</h2>
          <button
            onClick={close}
            className="p-1 rounded hover:bg-[#35343d] transition-colors text-[#c9c4d7]"
            aria-label="Close settings"
          >
            <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </header>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
          {/* Watched Folders */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-[#8b8fa8] uppercase mb-2">
              Watched Folders
            </label>
            <FolderManager />
            <IndexProgress />
          </section>

          {/* Inference Backend */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-[#8b8fa8] uppercase mb-2">
              Inference Backend
            </label>
            <div className="flex gap-2">
              <button
                onClick={() => void handleBackendSwitch("llamacpp")}
                disabled={switching || !isCloud}
                className={`flex-1 py-2 rounded-[6px] text-[12px] font-semibold transition-colors ${
                  !isCloud
                    ? "bg-[#242736] border border-[#94a3b8] text-[#e5e0ed]"
                    : "bg-[#1a1d27] border border-[#242736] text-[#474554] hover:border-[#474554]"
                }`}
              >
                Local
              </button>
              <button
                onClick={() => void handleBackendSwitch("claude")}
                disabled={switching || isCloud}
                className={`flex-1 py-2 rounded-[6px] text-[12px] font-semibold transition-colors ${
                  isCloud
                    ? "bg-[#2d1f4a] border border-[#a78bfa] text-[#a78bfa]"
                    : "bg-[#1a1d27] border border-[#242736] text-[#474554] hover:border-[#474554]"
                }`}
              >
                Claude API
              </button>
            </div>
            <p className="text-[10px] font-mono text-[#474554] mt-1 px-1">
              {isCloud
                ? "Restart backend to apply · set ANTHROPIC_API_KEY"
                : "Restart backend to apply · set CEREBRO_INFERENCE_BACKEND=claude"}
            </p>
          </section>

          {/* Model */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-[#8b8fa8] uppercase mb-2">
              Model
            </label>
            <ModelSelector />
          </section>

          {/* Fleet Orchestrator */}
          {!isCloud && (
            <section>
              <label className="block text-[11px] font-bold tracking-[0.05em] text-[#8b8fa8] uppercase mb-2">
                Fleet Orchestrator
              </label>
              <FleetSettings />
            </section>
          )}

          {/* Tool Permissions */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-[#8b8fa8] uppercase mb-2">
              Tool Permissions
            </label>
            <ToolPermissions />
          </section>

          {/* Notifications */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-[#8b8fa8] uppercase mb-2">
              Notifications
            </label>
            <DndToggle />
          </section>
        </div>

        {/* Status bar at bottom */}
        <footer className="h-[28px] bg-[#1a1d27] border-t border-[#242736] flex items-center justify-between px-3 shrink-0">
          <div className="flex items-center gap-1">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                isCloud ? "bg-[#a78bfa]" : status?.engine_ok ? "bg-[#4ade80]" : "bg-[#ffb4ab]"
              }`}
            />
            <span
              className={`text-[10px] font-bold tracking-[0.05em] uppercase ${
                isCloud ? "text-[#a78bfa]" : status?.engine_ok ? "text-[#4ade80]" : "text-[#ffb4ab]"
              }`}
            >
              {isCloud ? "Claude API" : status?.engine_ok ? "Engine OK" : "Engine down"}
            </span>
          </div>
        </footer>
      </aside>
    </div>
  );
}
