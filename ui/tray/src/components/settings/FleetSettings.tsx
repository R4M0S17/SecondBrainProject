import { useEffect, useState } from "react";
import { getFleetModels, setFleetMode } from "../../api/client";
import { useSystemStore } from "../../stores/system";
import type { FleetModelEntry } from "../../api/types";

export default function FleetSettings() {
  const fleetStatus = useSystemStore((s) => s.fleetStatus);
  const refreshFleet = useSystemStore((s) => s.refreshFleet);
  const [models, setModels] = useState<FleetModelEntry[]>([]);
  const [pinnedModelId, setPinnedModelId] = useState("");
  const [ramMargin, setRamMargin] = useState(15);
  const [applying, setApplying] = useState(false);

  const mode = fleetStatus?.mode ?? "auto";

  useEffect(() => {
    getFleetModels()
      .then((r) => {
        setModels(r.models);
        if (!pinnedModelId && r.active_model_id) setPinnedModelId(r.active_model_id);
      })
      .catch(() => {});
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

      {/* RAM safety margin — Auto mode only */}
      {mode === "auto" && (
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-mono text-outline">
            RAM safety margin · {ramMargin}%
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setRamMargin((v) => Math.max(5, v - 5))}
              className="w-6 h-6 flex items-center justify-center bg-background border border-outline-variant rounded text-on-surface-variant hover:border-outline transition-colors"
            >
              −
            </button>
            <button
              onClick={() => setRamMargin((v) => Math.min(50, v + 5))}
              className="w-6 h-6 flex items-center justify-center bg-background border border-outline-variant rounded text-on-surface-variant hover:border-outline transition-colors"
            >
              +
            </button>
          </div>
        </div>
      )}

      {/* Swap stats */}
      <p className="text-[10px] font-mono text-outline">
        {fleetStatus?.model_swaps_session ?? 0} swaps this session
      </p>
    </div>
  );
}
