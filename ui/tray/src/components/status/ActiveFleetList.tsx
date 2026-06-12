import { useCallback } from "react";
import { useSystemStore } from "../../stores/system";
import { useSettingsStore } from "../../stores/settings";
import type { LlamaCppModel } from "../../api/types";

export default function ActiveFleetList() {
  const status = useSystemStore((s) => s.status);
  const llamaCppModels = useSettingsStore((s) => s.llamaCppModels);
  const switchingModel = useSettingsStore((s) => s.switchingModel);
  const patch = useSettingsStore((s) => s.patch);

  const activeModelId = status?.current_model_id ?? status?.model;

  const handleSelect = useCallback(
    (modelName: string) => {
      if (modelName === activeModelId || switchingModel) return;
      patch({ model: modelName });
    },
    [activeModelId, switchingModel, patch]
  );

  if (llamaCppModels.length === 0) {
    return (
      <div>
        <h2 className="text-sm font-semibold tracking-wider text-on-surface-variant uppercase mb-4">
          Active Fleet
        </h2>
        <div className="p-3 rounded-lg border border-outline-variant/20 bg-surface-container/30 opacity-70 flex items-center justify-center">
          <span className="text-xs text-outline">No models available</span>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-sm font-semibold tracking-wider text-on-surface-variant uppercase mb-4">
        Active Fleet
      </h2>
      <div className="space-y-1">
        {llamaCppModels.map((m: LlamaCppModel) => {
          const isActive = m.name === activeModelId;
          return (
            <button
              key={m.name}
              onClick={() => handleSelect(m.name)}
              disabled={isActive || switchingModel}
              className={`w-full text-left px-3 rounded-md border flex items-center justify-between transition-all ${
                isActive
                  ? "border-primary-container bg-primary-container/10 py-3"
                  : "border-outline-variant/10 bg-surface-container/20 hover:bg-surface-container/40 cursor-pointer py-2"
              } ${switchingModel && !isActive ? "opacity-50" : ""}`}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                {isActive && (
                  <div className="w-2 h-2 rounded-full bg-primary-container glow-ring shrink-0" />
                )}
                <span
                  className={`truncate ${
                    isActive ? "text-[13px] text-on-surface font-semibold" : "text-[11px] text-on-surface-variant"
                  }`}
                >
                  {m.name}
                </span>
              </div>
              <span className={`font-label-mono shrink-0 ml-2 ${
                isActive ? "text-[11px] text-primary-container" : "text-[9px] text-outline"
              }`}>
                {m.size_gb.toFixed(1)}GB
              </span>
            </button>
          );
        })}
      </div>
      {switchingModel && (
        <p className="text-[10px] text-primary-container text-center pt-2 animate-pulse">
          Switching model…
        </p>
      )}
    </div>
  );
}
