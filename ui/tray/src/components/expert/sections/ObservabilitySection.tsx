import { useEffect, useState, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useSystemStore } from "../../../stores/system";
import { useDebugStore } from "../../../stores/debug";
import { useSettingsStore } from "../../../stores/settings";
import { getEmbeddingCacheStats, getConfig, updateConfig } from "../../../api/client";
import type { EmbeddingCacheStats, AppConfig } from "../../../api/types";

export default function ObservabilitySection() {
  const { t } = useTranslation();
  const status = useSystemStore((s) => s.status);
  const { close } = useSettingsStore();
  const { setDebugPanelOpen } = useDebugStore();
  const [cacheStats, setCacheStats] = useState<EmbeddingCacheStats | null>(null);
  const [logVerbose, setLogVerbose] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    (async () => {
      try {
        const [stats, cfg] = await Promise.all([
          getEmbeddingCacheStats().catch(() => null),
          getConfig().catch(() => null),
        ]);
        setCacheStats(stats);
        if (cfg?.log_verbose) setLogVerbose(true);
      } catch {}
    })();

    pollRef.current = setInterval(async () => {
      try {
        const stats = await getEmbeddingCacheStats();
        setCacheStats(stats);
      } catch {}
    }, 10000);

    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleOpenDebug = useCallback(() => {
    close();
    setDebugPanelOpen(true);
  }, [close, setDebugPanelOpen]);

  const handleOpenDataFolder = useCallback(async () => {
    try {
      const { open } = await import("@tauri-apps/plugin-shell");
      await open("~/.cerebro");
    } catch {
      window.alert("Open ~/.cerebro in Finder to view data files.");
    }
  }, []);

  const handleToggleLogVerbose = useCallback(async (v: boolean) => {
    setLogVerbose(v);
    try {
      await updateConfig({ log_verbose: v } as Partial<AppConfig>);
    } catch {}
  }, []);

  return (
    <div className="max-w-2xl space-y-8">
      {/* Time-Travel Debugger */}
      <section>
        <h3 className="text-[13px] font-semibold text-on-surface mb-3">
          {t("expert.observability.debugger")}
        </h3>
        <button
          onClick={handleOpenDebug}
          className="w-full flex items-center justify-between px-4 py-3 rounded-lg bg-surface-container-low hover:bg-surface-container border border-outline-variant/30 transition-colors text-left group"
        >
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-[18px] text-on-surface-variant group-hover:text-primary-container transition-colors">
              history
            </span>
            <div>
              <div className="text-[12px] font-medium text-on-surface">
                {t("settings.debug_title")}
              </div>
              <div className="text-[10px] text-on-surface-variant">
                {t("settings.debug_desc")}
              </div>
            </div>
          </div>
          <span className="material-symbols-outlined text-[16px] text-outline group-hover:text-primary-container transition-colors">
            open_in_new
          </span>
        </button>
      </section>

      {/* System Metrics */}
      <section>
        <h3 className="text-[13px] font-semibold text-on-surface mb-3">
          {t("expert.observability.metrics")}
        </h3>
        <div className="bg-surface-container-low border border-outline-variant/30 rounded-lg p-4 space-y-2">
          {status ? (
            <>
              <MetricRow
                label={t("expert.observability.ram")}
                value={`${status.ram_used_gb.toFixed(1)} / ${status.ram_total_gb.toFixed(1)} GB`}
              />
              <MetricRow
                label={t("expert.observability.latency")}
                value={`${status.avg_latency_ms} ms avg`}
              />
              <MetricRow
                label={t("expert.observability.tool_calls")}
                value={`${status.tool_call_count}`}
              />
              <MetricRow
                label={t("expert.observability.queries")}
                value={`${status.queries_total}`}
              />
              <MetricRow
                label={t("expert.observability.memory_hits")}
                value={`${status.memory_hits}`}
              />
              {cacheStats && (
                <>
                  <MetricRow
                    label={t("expert.observability.cache_hits")}
                    value={`${cacheStats.hits}`}
                  />
                  <MetricRow
                    label={t("expert.observability.cache_misses")}
                    value={`${cacheStats.misses}`}
                  />
                  <MetricRow
                    label={t("expert.observability.cache_hit_rate")}
                    value={`${cacheStats.hit_rate_percent.toFixed(1)}%`}
                  />
                  <MetricRow
                    label={t("expert.observability.cache_size")}
                    value={`${cacheStats.size} / ${cacheStats.max_size}`}
                  />
                </>
              )}
            </>
          ) : (
            <p className="text-[12px] text-outline">{t("expert.observability.no_data")}</p>
          )}
        </div>
      </section>

      {/* Verbose Logging */}
      <section>
        <h3 className="text-[13px] font-semibold text-on-surface mb-3">
          {t("expert.observability.logging")}
        </h3>
        <div className="bg-[#2a1e1e] border border-[#4a2e2e] rounded-lg px-4 py-2.5 mb-3">
          <p className="text-[11px] text-yellow-500 flex items-center gap-1.5">
            <span className="material-symbols-outlined text-[14px]">warning</span>
            {t("expert.observability.log_warning")}
          </p>
        </div>
        <label className="flex items-center justify-between px-3 py-2 rounded bg-surface-container-low cursor-pointer">
          <span className="text-[12px] text-on-surface-variant font-medium">
            {t("expert.observability.verbose_logging")}
          </span>
          <input
            type="checkbox"
            checked={logVerbose}
            onChange={(e) => handleToggleLogVerbose(e.target.checked)}
            className="accent-primary-container"
          />
        </label>
      </section>

      {/* Open Data Folder */}
      <section>
        <h3 className="text-[13px] font-semibold text-on-surface mb-3">
          {t("expert.observability.data_folder")}
        </h3>
        <button
          onClick={handleOpenDataFolder}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-lg bg-surface-container-low hover:bg-surface-container border border-outline-variant/30 transition-colors text-left group"
        >
          <span className="material-symbols-outlined text-[18px] text-on-surface-variant group-hover:text-primary-container transition-colors">
            folder_open
          </span>
          <div>
            <div className="text-[12px] font-medium text-on-surface">
              {t("expert.observability.open_data_folder")}
            </div>
            <div className="text-[10px] text-on-surface-variant">
              ~/.cerebro/
            </div>
          </div>
        </button>
      </section>
    </div>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[11px] text-outline">{label}</span>
      <span className="text-[12px] font-mono text-on-surface tabular-nums">{value}</span>
    </div>
  );
}
