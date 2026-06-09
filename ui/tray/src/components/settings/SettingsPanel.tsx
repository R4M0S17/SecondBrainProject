import { useEffect, useState } from "react";
import { useSettingsStore } from "../../stores/settings";
import { useSystemStore } from "../../stores/system";
import { switchInferenceBackend } from "../../api/client";
import FolderManager from "./FolderManager";
import IndexProgress from "./IndexProgress";
import ModelSelector from "./ModelSelector";
import ToolPermissions from "./ToolPermissions";
import DndToggle from "./DndToggle";
import FleetSettings from "./FleetSettings";

type BackendId = "llamacpp" | "mlx" | "claude";

const BACKENDS: { id: BackendId; label: string }[] = [
  { id: "llamacpp", label: "Local" },
  { id: "mlx", label: "MLX" },
  { id: "claude", label: "Claude API" },
];

export default function SettingsPanel() {
  const { close, isOpen } = useSettingsStore();
  const status = useSystemStore((s) => s.status);
  const activeBackend: BackendId = (status?.provider as BackendId) || "llamacpp";
  const [switching, setSwitching] = useState(false);

  const handleBackendSwitch = async (backend: BackendId) => {
    if (backend === activeBackend) return;
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
    <div className="fixed inset-0 z-[60] flex" role="complementary" aria-label="Settings">
      {/* Backdrop */}
      <div
        className="flex-1 bg-black/40"
        onClick={close}
        aria-hidden="true"
      />

      {/* Slide-over panel — 320px from right */}
      <aside
        className={`w-[320px] h-full bg-surface-container border-l border-outline-variant flex flex-col z-10 transition-transform duration-200 ease-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <header className="h-[48px] flex items-center justify-between px-4 bg-surface-container border-b border-outline-variant shrink-0">
          <h2 className="text-[15px] font-semibold text-on-surface">Settings</h2>
          <button
            onClick={close}
            className="p-1 rounded hover:bg-surface-container-highest transition-colors text-on-surface-variant"
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
            <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
              Watched Folders
            </label>
            <FolderManager />
            <IndexProgress />
          </section>

          {/* Inference Backend */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
              Inference Backend
            </label>
            <div className="flex gap-2">
              {BACKENDS.map(({ id, label }) => {
                const isActive = activeBackend === id;
                return (
                  <button
                    key={id}
                    onClick={() => void handleBackendSwitch(id)}
                    disabled={switching || isActive}
                    className={`flex-1 py-2 rounded-[6px] text-[12px] font-semibold transition-all ${
                      isActive
                        ? "bg-surface-container border border-primary-container text-on-surface shadow-sm"
                        : "bg-surface-container border border-outline-variant text-outline hover:border-outline hover:text-outline"
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </section>

          {/* Model */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
              Model
            </label>
            <ModelSelector />
          </section>

          {/* Fleet Orchestrator */}
          {activeBackend !== "claude" && (
            <section>
              <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
                Fleet Orchestrator
              </label>
              <FleetSettings />
            </section>
          )}

          {/* Tool Permissions */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
              Tool Permissions
            </label>
            <ToolPermissions />
          </section>

          {/* Notifications */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
              Notifications
            </label>
            <DndToggle />
          </section>
        </div>

        {/* Status bar at bottom */}
        <footer className="h-[28px] bg-surface-container border-t border-outline-variant flex items-center justify-between px-3 shrink-0">
          <div className="flex items-center gap-1">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                activeBackend === "claude" ? "bg-[#a78bfa]" : status?.engine_ok ? "bg-success-green" : "bg-error"
              }`}
            />
            <span
              className={`text-[10px] font-bold tracking-[0.05em] uppercase ${
                activeBackend === "claude" ? "text-[#a78bfa]" : status?.engine_ok ? "text-success-green" : "text-error"
              }`}
            >
              {activeBackend === "claude" ? "Claude API" : status?.engine_ok ? "Engine OK" : "Engine down"}
            </span>
          </div>
        </footer>
      </aside>
    </div>
  );
}
