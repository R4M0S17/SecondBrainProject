import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSettingsStore } from "../../stores/settings";
import { useSystemStore } from "../../stores/system";
import { switchInferenceBackend } from "../../api/client";
import FolderManager from "./FolderManager";
import IndexProgress from "./IndexProgress";
import ModelSelector from "./ModelSelector";
import ToolPermissions from "./ToolPermissions";
import FocusModeToggle from "./FocusModeToggle";
import NotificationsToggle from "./NotificationsToggle";
import FleetSettings from "./FleetSettings";
import ModelModeToggle from "./ModelModeToggle";
import KnowledgeSyncPanel from "./KnowledgeSyncPanel";
import ClaudeModelSection from "./ClaudeModelSection";
import ClaudeApiKeySection from "./ClaudeApiKeySection";

type BackendId = "llamacpp" | "mlx" | "claude";

const BACKENDS: { id: BackendId; label: string }[] = [
  { id: "llamacpp", label: "Local" },
  { id: "mlx", label: "MLX" },
  { id: "claude", label: "Claude API" },
];

const BACKEND_LS_KEY = "cerebro_selected_backend";

export default function SettingsPanel() {
  const { t, i18n } = useTranslation();
  const { close, isOpen, patch, config } = useSettingsStore();
  const status = useSystemStore((s) => s.status);
  const locale = config?.locale || "en";

  const handleLanguageChange = (lang: string) => {
    i18n.changeLanguage(lang);
    patch({ locale: lang });
  };

  // Local-selected backend (works offline, persisted)
  const [selectedBackend, setSelectedBackend] = useState<BackendId>(() => {
    const stored = localStorage.getItem(BACKEND_LS_KEY);
    if (stored === "llamacpp" || stored === "mlx" || stored === "claude") return stored;
    return "llamacpp";
  });

  // Sync from server when available
  const serverBackend = (status?.provider as BackendId) || null;
  useEffect(() => {
    if (serverBackend && serverBackend !== selectedBackend) {
      setSelectedBackend(serverBackend);
      localStorage.setItem(BACKEND_LS_KEY, serverBackend);
    }
  }, [serverBackend]);

  const [switching, setSwitching] = useState(false);
  const isClaude = selectedBackend === "claude";

  const handleBackendSwitch = async (backend: BackendId) => {
    if (backend === selectedBackend) return;
    setSelectedBackend(backend);
    localStorage.setItem(BACKEND_LS_KEY, backend);
    setSwitching(true);
    try {
      await switchInferenceBackend(backend);
    } catch {
      // Backend may be offline — selection is stored locally
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
          {/* Language / Idioma */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
              {t("settings.language")}
            </label>
            <select
              value={locale}
              onChange={(e) => handleLanguageChange(e.target.value)}
              className="w-full py-2 px-3 rounded-[6px] text-[13px] bg-surface-container border border-outline-variant text-on-surface focus:outline-none focus:border-primary"
            >
              <option value="en">English</option>
              <option value="es">Español</option>
            </select>
          </section>

          {/* Watched Folders */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
              {t("settings.watched_folders")}
            </label>
            <FolderManager />
            <IndexProgress />
          </section>

          {/* Inference Backend */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
              {t("settings.inference_backend")}
            </label>
            <div className="flex gap-2">
              {BACKENDS.map(({ id, label }) => {
                const isActive = selectedBackend === id;
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

          {isClaude ? (
            <>
              {/* ── Claude sections at top ── */}
              <ClaudeApiKeySection />
              <ClaudeModelSection />

              {/* ── Local model sections pushed to bottom ── */}
              <div className="pt-4 border-t border-outline-variant">
                <p className="text-[10px] font-bold tracking-[0.05em] text-outline uppercase mb-3">
                  {t("settings.model")}
                </p>
                <section>
                  <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
                    {t("settings.model")}
                  </label>
                  <ModelSelector />
                </section>
                <section className="mt-6">
                  <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
                    {t("settings.fleet")}
                  </label>
                  <FleetSettings />
                </section>
              </div>
            </>
          ) : (
            <>
              {/* ── Local model sections at top ── */}
              <section>
                <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
                  {t("settings.model")}
                </label>
                <div className="mt-3">
                  <ModelSelector />
                </div>
              </section>
              <section>
                <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
                  {t("settings.fleet")}
                </label>
                <FleetSettings />
              </section>

              {/* ── Claude section pushed to bottom ── */}
              <ClaudeApiKeySection />
            </>
          )}

          {/* Tool Permissions */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
              {t("settings.tool_permissions")}
            </label>
            <ToolPermissions />
          </section>

          {/* Knowledge Sync */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
              {t("settings.knowledge_sync")}
            </label>
            <KnowledgeSyncPanel />
          </section>

          {/* Focus Mode */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
              {t("settings.focus_mode")}
            </label>
            <FocusModeToggle />
          </section>

          {/* Notifications */}
          <section>
            <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
              {t("settings.notifications")}
            </label>
            <NotificationsToggle />
          </section>

          {/* Low Power Mode — always at bottom (in development) */}
          <ModelModeToggle />
        </div>

        {/* Status bar at bottom */}
        <footer className="h-[28px] bg-surface-container border-t border-outline-variant flex items-center justify-between px-3 shrink-0">
          <div className="flex items-center gap-1">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                isClaude ? "bg-[#a78bfa]" : status?.engine_ok ? "bg-success-green" : "bg-error"
              }`}
            />
            <span
              className={`text-[10px] font-bold tracking-[0.05em] uppercase ${
                isClaude ? "text-[#a78bfa]" : status?.engine_ok ? "text-success-green" : "text-error"
              }`}
            >
              {isClaude ? "Claude API" : status?.engine_ok ? "Engine OK" : "Engine down"}
            </span>
          </div>
        </footer>
      </aside>
    </div>
  );
}


