import { useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useSystemStore } from "../../stores/system";
import { useSettingsStore } from "../../stores/settings";
import type { LlamaCppModel } from "../../api/types";

export default function ActiveFleetList() {
  const { t } = useTranslation();
  const status = useSystemStore((s) => s.status);
  const health = useSystemStore((s) => s.health);
  const llamaCppModels = useSettingsStore((s) => s.llamaCppModels);
  const llamaCppLoading = useSettingsStore((s) => s.llamaCppLoading);
  const switchingModel = useSettingsStore((s) => s.switchingModel);
  const pendingModel = useSettingsStore((s) => s.pendingModel);
  const patch = useSettingsStore((s) => s.patch);
  const checkModelSwitch = useSettingsStore((s) => s.checkModelSwitch);

  const activeModelId = status?.current_model_id ?? status?.model;

  useEffect(() => {
    checkModelSwitch(status, health);
  }, [status, health, checkModelSwitch]);

  const handleSelect = useCallback(
    (modelName: string) => {
      if (modelName === activeModelId || switchingModel) return;
      patch({ model: modelName });
    },
    [activeModelId, switchingModel, patch]
  );

  if (llamaCppLoading) {
    return (
      <div>
        <h2 className="text-sm font-semibold tracking-wider text-on-surface-variant uppercase mb-4">
          {t("fleet.active")}
        </h2>
        <div className="p-3 rounded-lg border border-outline-variant/20 bg-surface-container/30 flex items-center justify-center gap-2">
          <span className="inline-block w-3 h-3 border-2 border-outline border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-outline">{t("fleet.loading")}</span>
        </div>
      </div>
    );
  }

  if (llamaCppModels.length === 0) {
    return (
      <div>
        <h2 className="text-sm font-semibold tracking-wider text-on-surface-variant uppercase mb-4">
          {t("fleet.active")}
        </h2>
        <div className="p-3 rounded-lg border border-outline-variant/20 bg-surface-container/30 opacity-70 flex items-center justify-center">
          <span className="text-xs text-outline">{t("fleet.no_models")}</span>
        </div>
      </div>
    );
  }

  const switchingTarget = pendingModel ?? null;
  const engineIsUp = health?.llama_server === "up";

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold tracking-wider text-on-surface-variant uppercase">
          {t("fleet.active")}
        </h2>
        {switchingModel && (
          <span className="text-[10px] text-amber-400 font-label-mono animate-pulse">
            switching...
          </span>
        )}
      </div>

      {/* Current Model */}
      <div className="mb-4">
        <div className="text-[10px] font-bold tracking-[0.1em] text-outline uppercase mb-2">
          {t("fleet.current")}
        </div>
        <div className={`w-full px-3 py-3 rounded-lg border flex items-center justify-between transition-all ${
          switchingModel
            ? "border-amber-400/40 bg-amber-400/10"
            : engineIsUp
              ? "border-primary-container/40 bg-primary-container/15"
              : "border-outline-variant/20 bg-surface-container/30"
        }`}>
          <div className="flex items-center gap-2.5 min-w-0">
            <div className={`w-2 h-2 rounded-full shrink-0 ${
              switchingModel
                ? "bg-amber-400 animate-pulse"
                : engineIsUp
                  ? "bg-primary-container glow-ring"
                  : "bg-red-400"
            }`} />
            <span className="text-[13px] text-on-surface font-semibold truncate">
              {switchingModel && switchingTarget
                ? switchingTarget
                : activeModelId ?? "—"}
            </span>
          </div>
          {switchingModel ? (
            <span className="inline-block w-3.5 h-3.5 border-2 border-amber-400 border-t-transparent rounded-full animate-spin shrink-0 ml-2" />
          ) : (
            <span className="text-[11px] font-label-mono text-primary-container shrink-0 ml-2">
              {(() => {
                const m = llamaCppModels.find((x) => x.name === activeModelId);
                return m ? `${m.size_gb.toFixed(1)}GB` : "—";
              })()}
            </span>
          )}
        </div>
        {switchingModel && (
          <p className="text-[10px] text-amber-400/80 mt-1.5 text-center">
            {t("fleet.switching")}
          </p>
        )}
        {!switchingModel && !engineIsUp && health && (
          <p className="text-[10px] text-red-400/80 mt-1.5 text-center">
            {health.llama_server === "restarting" ? t("status.engine_restarting") : t("status.engine_down")}
          </p>
        )}
      </div>

      {/* Available Models */}
      {llamaCppModels.length > 1 && (
        <div>
          <div className="text-[10px] font-bold tracking-[0.1em] text-outline uppercase mb-2">
            {t("fleet.available")}
          </div>
          <div className="space-y-1">
            {llamaCppModels
              .filter((m) => m.name !== activeModelId)
              .map((m: LlamaCppModel) => (
                <button
                  key={m.name}
                  onClick={() => handleSelect(m.name)}
                  disabled={switchingModel}
                  className={`w-full text-left px-3 rounded-md border flex items-center justify-between transition-all ${
                    m.name === switchingTarget
                      ? "border-amber-400/30 bg-amber-400/10"
                      : "border-outline-variant/10 bg-surface-container/20 hover:bg-surface-container/40"
                  } ${switchingModel ? "opacity-50 cursor-not-allowed" : "cursor-pointer py-2"}`}
                >
                  <span className="text-[11px] text-on-surface-variant truncate flex items-center gap-2">
                    {m.name === switchingTarget && (
                      <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse shrink-0" />
                    )}
                    {m.name}
                  </span>
                  <span className="text-[9px] font-label-mono text-outline shrink-0 ml-2">
                    {m.size_gb.toFixed(1)}GB
                  </span>
                </button>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
