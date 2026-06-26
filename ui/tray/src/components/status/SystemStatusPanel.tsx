import { useTranslation } from "react-i18next";
import { useSystemStore } from "../../stores/system";

export default function SystemStatusPanel() {
  const { t } = useTranslation();
  const status = useSystemStore((s) => s.status);
  const health = useSystemStore((s) => s.health);

  if (!status) {
    return (
      <div className="bg-surface-container/40 rounded-xl p-4 border border-outline-variant/20 mb-6">
        <h2 className="text-sm font-semibold tracking-wider text-on-surface-variant uppercase mb-4">
          System Status
        </h2>
        <div className="text-[11px] text-outline/40 animate-pulse">{t("status.connecting")}</div>
      </div>
    );
  }

  const ramUsed = status.ram_used_gb ?? 0;
  const ramTotal = status.ram_total_gb ?? (ramUsed + (status.ram_available_gb ?? 0));
  const ramPercent = ramTotal > 0 ? (ramUsed / ramTotal) * 100 : 0;
  const pressure =
    status.ram_pressure === "critical" ? "critical" :
    status.ram_pressure === "warn" ? "warn" : "ok";

  const pressureColor =
    pressure === "critical" ? "text-error" :
    pressure === "warn" ? "text-amber-400" :
    "text-green-400";

  const engineDotColor =
    health?.llama_server === "up" ? "bg-green-400" :
    health?.llama_server === "restarting" ? "bg-amber-400" :
    "bg-red-400";

  const engineLabel =
    health?.llama_server === "up" ? t("status.engine_ok") :
    health?.llama_server === "restarting" ? t("status.engine_restarting") :
    t("status.engine_down");

  const providerBadge = status.provider === "claude" ? "text-purple-400" :
    status.provider === "mlx" ? "text-cyan-400" :
    "text-blue-400";

  const memBarColor =
    ramPercent > 80 ? "bg-error" :
    ramPercent > 60 ? "bg-amber-400" :
    "bg-green-400";

  return (
    <div className="mb-6">
      <h2 className="text-sm font-semibold tracking-wider text-on-surface-variant uppercase mb-4">
        System Status
      </h2>
      <div className="bg-surface-container/40 rounded-xl p-4 border border-outline-variant/20 space-y-3">
        {/* Engine + Latency */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`inline-block w-2 h-2 rounded-full ${engineDotColor} ${health?.llama_server === "up" ? "shadow-[0_0_6px] shadow-green-400/60" : ""}`} />
            <span className="text-[12px] font-medium text-on-surface">{engineLabel}</span>
            {status.provider && (
              <span className={`text-[9px] uppercase tracking-wider font-semibold ${providerBadge}`}>
                {status.provider}
              </span>
            )}
          </div>
          {status.avg_latency_ms > 0 && (
            <span className="text-[10px] font-label-mono text-outline tabular-nums">
              {Math.round(status.avg_latency_ms)}ms avg
            </span>
          )}
        </div>

        {/* Model */}
        <div className="flex items-center gap-1.5">
          <span className="material-symbols-outlined text-[14px] text-outline">neurology</span>
          <span className="text-[12px] text-on-surface truncate" title={status.model}>
            {status.model}
          </span>
        </div>

        {/* Memory */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[14px] text-outline">memory</span>
              <span className="text-[11px] font-label-mono text-on-surface tabular-nums">
                {ramUsed.toFixed(1)} / {ramTotal.toFixed(1)} GB
              </span>
            </div>
            <span className={`text-[10px] font-semibold font-label-mono ${pressureColor}`}>
              {Math.round(ramPercent)}%
              {pressure !== "ok" && (pressure === "critical" ? " !" : " \u2022")}
            </span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-outline/10 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ${memBarColor}`}
              style={{ width: `${Math.min(ramPercent, 100)}%` }}
            />
          </div>
        </div>

        {/* Indexed files + Queries */}
        <div className="flex items-center gap-3 text-[10px] text-outline font-label-mono pt-0.5">
          {status.indexed_files > 0 && (
            <span className="flex items-center gap-1">
              <span className="material-symbols-outlined text-[12px]">description</span>
              {status.indexed_files} file{status.indexed_files !== 1 ? "s" : ""}
            </span>
          )}
          {status.queries_total > 0 && (
            <span className="flex items-center gap-1">
              <span className="material-symbols-outlined text-[12px]">chat</span>
              {status.queries_total} query{status.queries_total !== 1 ? "ies" : "y"}
            </span>
          )}
          {status.tool_call_count > 0 && (
            <span className="flex items-center gap-1">
              <span className="material-symbols-outlined text-[12px]">build</span>
              {status.tool_call_count} tool{status.tool_call_count !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
