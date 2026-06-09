import { useEffect } from "react";
import { useSystemStore, selectLlamaServerState } from "../../stores/system";
import { useServicesStore } from "../../stores/services";
import EngineIndicator from "./EngineIndicator";

export default function StatusBar() {
  const startPolling = useSystemStore((s) => s.startPolling);
  useEffect(() => {
    startPolling(10_000);
  }, [startPolling]);

  const status = useSystemStore((s) => s.status);
  const servicesOff = useServicesStore((s) => s.servicesOff);
  const llamaServer = selectLlamaServerState(useSystemStore.getState());

  const engineOk = status?.engine_ok ?? false;
  const ramUsed = status?.ram_used_gb ?? 0;
  const ramTotal = status?.ram_total_gb ?? (status?.ram_used_gb ?? 0) + (status?.ram_available_gb ?? 0);
  const cpuAvg = 0;
  const uptime = "—";

  return (
    <footer className="fixed bottom-0 left-0 w-full flex justify-between items-center px-4 md:px-6 py-1 z-50 bg-surface-container-lowest/50 backdrop-blur-sm border-t border-outline-variant/10 text-on-surface-variant/70 text-[11px] font-label-mono shrink-0">
      <div className="flex items-center gap-2">
        <span>Cerebro OS</span>
        <span className="opacity-30">•</span>
        <EngineIndicator
          ok={engineOk}
          provider={status?.provider}
          llamaServer={llamaServer}
          servicesOff={servicesOff}
        />
      </div>
      <div className="flex gap-4">
        <span>RAM {ramUsed.toFixed(1)}/{ramTotal.toFixed(1)}GB</span>
        {cpuAvg > 0 && <span>CPU {Math.round(cpuAvg)}%</span>}
        <span>Uptime {uptime}</span>
      </div>
    </footer>
  );
}
