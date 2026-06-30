import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSettingsStore } from "../../stores/settings";
import { useSystemStore } from "../../stores/system";
import { useDebugStore } from "../../stores/debug";
import { switchInferenceBackend } from "../../api/client";
import FolderManager from "./FolderManager";
import IndexProgress from "./IndexProgress";
import ToggleSwitch from "../shared/ToggleSwitch";
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
  const { close, isOpen, patch, config, openExpert, models, activeModel, llamaCppModels } = useSettingsStore();
  const status = useSystemStore((s) => s.status);
  const locale = config?.locale || "en";

  const activeModelInfo = useMemo(() => {
    const found = llamaCppModels.find((m) => m.name.toLowerCase() === activeModel?.toLowerCase());
    if (found) return { name: found.name, size: `${found.size_gb.toFixed(1)} GB` };
    const inModels = models.find((m) => m.name.toLowerCase() === activeModel?.toLowerCase());
    if (inModels) return { name: inModels.name, size: inModels.size_gb > 0 ? `${inModels.size_gb.toFixed(1)} GB` : "GGUF" };
    return { name: activeModel ?? "—", size: "" };
  }, [llamaCppModels, models, activeModel]);

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
        <div className="flex-1 overflow-y-auto p-4 space-y-5 custom-scrollbar">
          {/* ═══════════════════════════════════════════ GENERAL ═══════════════════════════════════════════ */}
          <div>
            <div className="text-[10px] font-bold tracking-[0.08em] text-outline uppercase mb-2">General</div>
            <section>
              <label className="block text-[11px] font-medium text-on-surface-variant mb-1.5">
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
          </div>

          {/* ═══════════════════════════════════════════ AI ENGINE ═══════════════════════════════════════════ */}
          <div>
            <div className="text-[10px] font-bold tracking-[0.08em] text-outline uppercase mb-2">AI Engine</div>
            <div className="space-y-4">
              {/* Backend selector */}
              <section>
                <label className="block text-[11px] font-medium text-on-surface-variant mb-1.5">
                  {t("settings.inference_backend")}
                </label>
                <div className="flex gap-1.5 p-1 rounded-lg bg-surface-container-low">
                  {BACKENDS.map(({ id, label }) => {
                    const isActive = selectedBackend === id;
                    return (
                      <button
                        key={id}
                        onClick={() => void handleBackendSwitch(id)}
                        disabled={switching || isActive}
                        className={`flex-1 py-1.5 rounded-[6px] text-[12px] font-semibold transition-all ${
                          isActive
                            ? "bg-primary text-on-primary shadow-sm"
                            : "bg-transparent text-on-surface-variant hover:text-on-surface"
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
                  <ClaudeApiKeySection />
                  <ClaudeModelSection />
                  <section>
                    <label className="block text-[11px] font-medium text-on-surface-variant mb-1.5">
                      {t("settings.model")}
                    </label>
                    <ActiveModelDisplay name={activeModelInfo.name} size={activeModelInfo.size} />
                  </section>
                  <section>
                    <label className="block text-[11px] font-medium text-on-surface-variant mb-1.5">
                      {t("settings.fleet")}
                    </label>
                    <FleetSettings />
                  </section>
                </>
              ) : (
                <>
                  <section>
                    <label className="block text-[11px] font-medium text-on-surface-variant mb-1.5">
                      {t("settings.model")}
                    </label>
                    <ActiveModelDisplay name={activeModelInfo.name} size={activeModelInfo.size} />
                  </section>
                  <section>
                    <label className="block text-[11px] font-medium text-on-surface-variant mb-1.5">
                      {t("settings.fleet")}
                    </label>
                    <FleetSettings />
                  </section>
                  <ClaudeApiKeySection />
                </>
              )}
            </div>
          </div>

          {/* ═══════════════════════════════════════════ KNOWLEDGE ═══════════════════════════════════════════ */}
          <div>
            <div className="text-[10px] font-bold tracking-[0.08em] text-outline uppercase mb-2">Knowledge</div>
            <div className="space-y-4">
              <section>
                <label className="block text-[11px] font-medium text-on-surface-variant mb-1.5">
                  {t("settings.watched_folders")}
                </label>
                <FolderManager />
                <IndexProgress />
              </section>
              <section>
                <label className="block text-[11px] font-medium text-on-surface-variant mb-1.5">
                  {t("settings.knowledge_sync")}
                </label>
                <KnowledgeSyncPanel />
              </section>
            </div>
          </div>

          {/* ═══════════════════════════════════════════ PREFERENCES ═══════════════════════════════════════════ */}
          <div>
            <div className="text-[10px] font-bold tracking-[0.08em] text-outline uppercase mb-2">Preferences</div>
            <div className="space-y-px rounded-lg overflow-hidden border border-outline-variant/40">
              <div className="flex items-center justify-between px-3 py-2.5 bg-surface-container-low">
                <div className="flex items-center gap-2.5">
                  <span className="material-symbols-outlined text-[18px] text-on-surface-variant">do_not_disturb</span>
                  <span className="text-[12px] font-medium text-on-surface">{t("settings.focus_mode")}</span>
                </div>
                <ToggleSwitch
                  enabled={config?.focus_mode ?? false}
                  onChange={(v) => void patch({ focus_mode: v })}
                  size="sm"
                  ariaLabel={t("settings.focus_mode")}
                  className="bg-background"
                  knobClassName="shadow"
                />
              </div>
              <div className="flex items-center justify-between px-3 py-2.5 bg-surface-container-low border-t border-outline-variant/20">
                <div className="flex items-center gap-2.5">
                  <span className="material-symbols-outlined text-[18px] text-on-surface-variant">notifications</span>
                  <span className="text-[12px] font-medium text-on-surface">{t("settings.notifications")}</span>
                </div>
                <ToggleSwitch
                  enabled={config?.dnd_enabled ?? false}
                  onChange={(v) => void patch({ dnd_enabled: v })}
                  size="sm"
                  ariaLabel={t("settings.notifications")}
                  className="bg-background"
                  knobClassName="shadow"
                />
              </div>
            </div>
          </div>

          {/* ═══════════════════════════════════════════ DEVELOPER ═══════════════════════════════════════════ */}
          <div>
            <div className="text-[10px] font-bold tracking-[0.08em] text-outline uppercase mb-2">Developer</div>
            <div className="space-y-px rounded-lg overflow-hidden border border-outline-variant/40">
              <button
                onClick={() => {
                  const { close } = useSettingsStore.getState();
                  close();
                  useDebugStore.getState().setDebugPanelOpen(true);
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 bg-surface-container-low hover:bg-surface-container transition-colors text-left group"
              >
                <span className="material-symbols-outlined text-[18px] text-on-surface-variant group-hover:text-primary transition-colors">history</span>
                <span className="text-[12px] font-medium text-on-surface flex-1">{t("settings.debug_title")}</span>
                <span className="material-symbols-outlined text-[16px] text-outline group-hover:text-primary transition-colors">chevron_right</span>
              </button>
              <button
                onClick={() => openExpert()}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 bg-surface-container-low hover:bg-surface-container border-t border-outline-variant/20 transition-colors text-left group"
              >
                <span className="material-symbols-outlined text-[18px] text-on-surface-variant group-hover:text-primary transition-colors">tune</span>
                <span className="text-[12px] font-medium text-on-surface flex-1">{t("settings.expert_title")}</span>
                <span className="material-symbols-outlined text-[16px] text-outline group-hover:text-primary transition-colors">chevron_right</span>
              </button>
            </div>
          </div>

          {/* Low Power Mode */}
          <ModelModeToggle />
        </div>

        {/* Status bar at bottom */}
        <footer className="h-[36px] bg-surface-container border-t border-outline-variant flex items-center justify-between px-3 shrink-0">
          <div className="flex items-center gap-2">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                isClaude ? "bg-[#a78bfa]" : status?.engine_ok ? "bg-success-green" : "bg-error"
              }`}
            />
            <span
              className={`text-[11px] font-medium ${
                isClaude ? "text-[#a78bfa]" : status?.engine_ok ? "text-success-green" : "text-error"
              }`}
            >
              {isClaude ? "Claude API" : status?.engine_ok ? "Engine OK" : "Engine down"}
            </span>
          </div>
          <span className="text-[10px] text-outline">v0.4.2</span>
        </footer>
      </aside>
    </div>
  );
}

function ActiveModelDisplay({ name, size }: { name: string; size: string }) {
  const displayName = name.replace(/\.gguf$/i, "");
  return (
    <div className="flex items-center justify-between px-3 py-2 rounded-[6px] bg-surface-container border border-outline-variant">
      <div className="flex items-center gap-2 min-w-0">
        <div className="flex flex-col min-w-0">
          <span className="text-[12px] font-medium text-on-surface truncate">{displayName}</span>
          {size && <span className="text-[9px] font-mono text-on-surface-variant">{size}</span>}
        </div>
      </div>
      <span className="bg-surface-container-higher px-1.5 py-0.5 rounded text-[10px] font-mono text-on-surface-variant shrink-0 ml-2">
        GGUF
      </span>
    </div>
  );
}


