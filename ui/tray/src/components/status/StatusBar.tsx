import { useEffect, useState } from "react";
import { updateConfig } from "../../api/client";
import {
  useSystemStore,
  selectIsClaudeMode,
  selectRamPressure,
  selectSwapInProgress,
  selectLlamaServerState,
} from "../../stores/system";
import EngineIndicator from "./EngineIndicator";
import RamGauge from "./RamGauge";
import LatencyBadge from "./LatencyBadge";
import FilesCounter from "./FilesCounter";
import ModelBadge from "./ModelBadge";
import VramGauge from "./VramGauge";
import FleetPanel from "./FleetPanel";

export default function StatusBar() {
  const { status, health, fleetStatus, startPolling } = useSystemStore();
  const llamaServer = selectLlamaServerState(useSystemStore.getState());
  const swapInProgress = useSystemStore(selectSwapInProgress);
  const [fleetPanelOpen, setFleetPanelOpen] = useState(false);

  async function applyLiteProfileFromStatus(): Promise<void> {
    try {
      await updateConfig({
        inference_backend: "llamacpp",
        model: "Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        mlx_enabled: false,
      });
    } catch (e) {
      console.error("lite profile save failed", e);
    }
  }

  useEffect(() => {
    startPolling(10_000);
  }, [startPolling]);

  const isCloud = selectIsClaudeMode(status);

  const engineOk = status?.engine_ok ?? false;
  const modelId = status?.current_model_id ?? status?.model ?? "—";
  const quantization = status?.quantization ?? "";
  const files = status?.indexed_files ?? 0;
  const ramUsed = status?.ram_used_gb ?? 0;
  const ramTotal =
    status?.ram_total_gb ??
    (status?.ram_used_gb ?? 0) + (status?.ram_available_gb ?? 0);
  const ramPressure = selectRamPressure(status);
  const p95 = (status?.p95_latency_ms ?? 0) / 1000;
  const queries = status?.queries_total ?? 0;

  const hw = fleetStatus?.hardware;
  const vramUsed = hw ? hw.gpu_vram_total_gb - hw.gpu_vram_available_gb : 0;
  const showVram = hw && hw.gpu_backend !== "none";

  return (
    <footer
      className="flex justify-between items-center w-full px-3 bg-[#1c1b23] border-t border-[#242736] h-[28px] shrink-0 font-mono text-[10px] text-[#c9c4d7] uppercase tracking-wider"
      aria-label="System status"
    >
      {/* Left group */}
      <div className="flex items-center gap-3">
        <EngineIndicator ok={engineOk} provider={status?.provider} llamaServer={llamaServer} />
        <span className="opacity-20">•</span>
        <ModelBadge
          modelId={modelId}
          quantization={quantization}
          swapInProgress={swapInProgress}
          onClick={() => setFleetPanelOpen(true)}
        />
        <span className="opacity-20">•</span>
        <FilesCounter count={files} />
      </div>

      {/* Right group */}
      <div className="flex items-center gap-3">
        {isCloud ? (
          <span className="opacity-60">cloud inference</span>
        ) : (
          <>
            <RamGauge
              used={ramUsed}
              total={ramTotal}
              ramPressure={ramPressure}
              onApplyLiteProfile={applyLiteProfileFromStatus}
            />
            {showVram && (
              <>
                <span className="opacity-20">·</span>
                <VramGauge
                  used={vramUsed}
                  total={hw!.gpu_vram_total_gb}
                  unified={hw!.unified_memory}
                />
              </>
            )}
            <span className="opacity-20">•</span>
          </>
        )}
        <LatencyBadge p95={p95} />
        <span className="opacity-20">•</span>
        <span>{queries} queries</span>
      </div>

      <FleetPanel open={fleetPanelOpen} onClose={() => setFleetPanelOpen(false)} />
    </footer>
  );
}
