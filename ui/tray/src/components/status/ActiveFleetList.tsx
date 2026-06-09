import { useSystemStore } from "../../stores/system";
import { useSettingsStore } from "../../stores/settings";
import type { LlamaCppModel } from "../../api/types";

export default function ActiveFleetList() {
  const fleetStatus = useSystemStore((s) => s.fleetStatus);
  const status = useSystemStore((s) => s.status);
  const llamaCppModels = useSettingsStore((s) => s.llamaCppModels);

  const currentModel = fleetStatus?.current_model;
  const activeModelId = status?.current_model_id ?? status?.model;

  const otherModels = llamaCppModels.filter(
    (m: LlamaCppModel) => m.name !== activeModelId
  );

  return (
    <div>
      <h2 className="text-sm font-semibold tracking-wider text-on-surface-variant uppercase mb-4">
        Active Fleet
      </h2>
      <div className="space-y-3">
        {currentModel ? (
          <div className="p-3 rounded-lg border border-primary-container/30 bg-primary-container/5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-primary-container glow-ring" />
              <div>
                <div className="text-xs font-medium text-on-surface">{currentModel.id}</div>
                <div className="text-[10px] text-outline font-label-mono mt-0.5">
                  {status?.provider ?? "llama.cpp"} • {currentModel.params_b ? `${currentModel.params_b}B` : "—"}
                </div>
              </div>
            </div>
            {currentModel.quant && (
              <span className="text-[10px] bg-surface px-1.5 py-0.5 rounded border border-outline-variant font-label-mono">
                {currentModel.quant}
              </span>
            )}
          </div>
        ) : (
          <div className="p-3 rounded-lg border border-outline-variant/20 bg-surface-container/30 opacity-70 flex items-center justify-center">
            <span className="text-xs text-outline">No active models</span>
          </div>
        )}

        {otherModels.length > 0 && (
          <div className="pt-2">
            <h3 className="text-[10px] font-semibold tracking-wider text-outline uppercase mb-2">
              Available Models
            </h3>
            <div className="space-y-1">
              {otherModels.slice(0, 5).map((m: LlamaCppModel) => (
                <div
                  key={m.name}
                  className="px-3 py-1.5 rounded-md bg-surface-container/20 border border-outline-variant/10 flex items-center justify-between"
                >
                  <span className="text-[11px] text-on-surface-variant truncate max-w-[180px]">
                    {m.name}
                  </span>
                  <span className="text-[9px] text-outline font-label-mono shrink-0 ml-2">
                    {m.size_gb.toFixed(1)}GB
                  </span>
                </div>
              ))}
              {otherModels.length > 5 && (
                <p className="text-[10px] text-outline text-center pt-1">
                  +{otherModels.length - 5} more
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
