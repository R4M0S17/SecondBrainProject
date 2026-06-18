import { useEffect, useState } from "react";
import { getFleetModels, setFleetMode } from "../../api/client";
import { useSystemStore } from "../../stores/system";
import type { FleetModelEntry } from "../../api/types";

export default function FleetSettings() {
  const fleetStatus = useSystemStore((s) => s.fleetStatus);
  const refreshFleet = useSystemStore((s) => s.refreshFleet);
  const [models, setModels] = useState<FleetModelEntry[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [pinnedModelId, setPinnedModelId] = useState("");
  const [applying, setApplying] = useState(false);

  const mode = fleetStatus?.mode ?? "auto";

  useEffect(() => {
    setModelsLoading(true);
    getFleetModels()
      .then((r) => {
        setModels(r.models);
        if (!pinnedModelId && r.active_model_id) setPinnedModelId(r.active_model_id);
      })
      .catch(() => {})
      .finally(() => setModelsLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const switchMode = async (next: "auto" | "pinned") => {
    setApplying(true);
    try {
      await setFleetMode(next, next === "pinned" ? pinnedModelId : undefined);
      await refreshFleet();
    } finally {
      setApplying(false);
    }
  };

  const handlePinnedModel = async (id: string) => {
    setPinnedModelId(id);
    setApplying(true);
    try {
      await setFleetMode("pinned", id);
      await refreshFleet();
    } finally {
      setApplying(false);
    }
  };

  // Group models by family for <optgroup>
  const byFamily = models.reduce<Record<string, FleetModelEntry[]>>((acc, m) => {
    (acc[m.family] ??= []).push(m);
    return acc;
  }, {});

  return (
    <div className="space-y-3">
      {modelsLoading ? (
        <div className="flex items-center gap-2 py-3 text-[12px] text-outline">
          <span className="inline-block w-3 h-3 border-2 border-outline border-t-transparent rounded-full animate-spin" />
          Loading models…
        </div>
      ) : (
        <>
          {/* Mode toggle */}
          <div className="flex gap-2">
            {(["auto", "pinned"] as const).map((opt) => (
              <button
                key={opt}
                onClick={() => void switchMode(opt)}
                disabled={applying || mode === opt}
                className={`flex-1 py-2 rounded-[6px] text-[12px] font-semibold capitalize transition-colors ${
                  mode === opt
                    ? "bg-surface-container border border-primary-container text-on-surface"
                    : "bg-surface-container border border-outline-variant text-outline hover:border-outline"
                }`}
              >
                {opt}
              </button>
            ))}
          </div>

          {/* Model picker — Pinned mode only */}
          {mode === "pinned" && (
            <select
              value={pinnedModelId}
              onChange={(e) => void handlePinnedModel(e.target.value)}
              disabled={applying}
              className="w-full bg-background border border-outline-variant rounded px-2 py-1.5 text-[12px] font-mono text-on-surface-variant focus:outline-none focus:border-outline"
            >
              {Object.entries(byFamily).map(([family, entries]) => (
                <optgroup key={family} label={family}>
                  {entries.map((m) => (
                    <option key={m.id} value={m.id} disabled={!m.available_on_disk}>
                      {m.id} · {m.params_b}B · {m.quant} · {m.ram_required_gb}GB
                      {!m.available_on_disk ? " (not found)" : ""}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          )}

          {/* Swap stats */}
          <p className="text-[10px] font-mono text-outline">
            {fleetStatus?.model_swaps_session ?? 0} swaps this session
          </p>
        </>
      )}
    </div>
  );
}
