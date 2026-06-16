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

  const activeModel = llamaCppModels.find((m) => m.name === activeModelId);
  const availableModels = llamaCppModels.filter((m) => m.name !== activeModelId);

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

      {/* Current Model */}
      {activeModel && (
        <div className="mb-4">
          <div className="text-[10px] font-bold tracking-[0.1em] text-outline uppercase mb-2">
            Current Model
          </div>
          <div className="w-full px-3 py-3 rounded-lg border border-primary-container/40 bg-primary-container/15 flex items-center justify-between">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-2 h-2 rounded-full bg-primary-container glow-ring shrink-0" />
              <span className="text-[13px] text-on-surface font-semibold truncate">
                {activeModel.name}
              </span>
            </div>
            <span className="text-[11px] font-label-mono text-primary-container shrink-0 ml-2">
              {activeModel.size_gb.toFixed(1)}GB
            </span>
          </div>
        </div>
      )}

      {/* Available Models */}
      {availableModels.length > 0 && (
        <div>
          <div className="text-[10px] font-bold tracking-[0.1em] text-outline uppercase mb-2">
            Available Models
          </div>
          <div className="space-y-1">
            {availableModels.map((m: LlamaCppModel) => (
              <button
                key={m.name}
                onClick={() => handleSelect(m.name)}
                disabled={switchingModel}
                className={`w-full text-left px-3 rounded-md border flex items-center justify-between transition-all ${
                  "border-outline-variant/10 bg-surface-container/20 hover:bg-surface-container/40 cursor-pointer py-2"
                } ${switchingModel ? "opacity-50" : ""}`}
              >
                <span className="text-[11px] text-on-surface-variant truncate">
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

      {switchingModel && (
        <p className="text-[10px] text-primary-container text-center pt-2 animate-pulse">
          Switching model…
        </p>
      )}
    </div>
  );
}
