import { useEffect, useState, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { getConfig, updateConfig, getFleetStatus } from "../../../api/client";
import type { AppConfig, FleetStatus as FleetStatusType } from "../../../api/types";
import ToggleSwitch from "../../shared/ToggleSwitch";

interface FleetField {
  key: keyof AppConfig;
  type: "float" | "int" | "bool" | "select";
  defaultVal: number | boolean | string;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
}

const FIELDS: FleetField[] = [
  { key: "ram_primary_gb", type: "float", defaultVal: 1.0, min: 0.1, max: 8.0, step: 0.1 },
  { key: "ram_fallback_gb", type: "float", defaultVal: 0.3, min: 0.1, max: 4.0, step: 0.1 },
  { key: "ram_min_available_gb", type: "float", defaultVal: 0.5, min: 0.1, max: 4.0, step: 0.1 },
  { key: "swap_timeout", type: "int", defaultVal: 60, min: 10, max: 600 },
  { key: "llamacpp_simple", type: "bool", defaultVal: true },
  { key: "mlx_enabled", type: "select", defaultVal: "auto", options: ["auto", "true", "false"] },
];

export default function FleetSection() {
  const { t } = useTranslation();
  const [params, setParams] = useState<Record<string, number | boolean | string>>({});
  const [fleetStatus, setFleetStatus] = useState<FleetStatusType | null>(null);
  const [loaded, setLoaded] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const statusIntervalRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    (async () => {
      try {
        const [cfg, fs] = await Promise.all([
          getConfig(),
          getFleetStatus().catch(() => null),
        ]);
        const p: Record<string, number | boolean | string> = {};
        for (const f of FIELDS) {
          const val = cfg[f.key];
          p[f.key] = (val !== undefined && val !== null)
            ? (val as number | boolean | string)
            : f.defaultVal;
        }
        setParams(p);
        setFleetStatus(fs);
        setLoaded(true);
      } catch {
        const p: Record<string, number | boolean | string> = {};
        for (const f of FIELDS) p[f.key] = f.defaultVal;
        setParams(p);
        setLoaded(true);
      }
    })();

    statusIntervalRef.current = setInterval(async () => {
      try {
        const fs = await getFleetStatus();
        setFleetStatus(fs);
      } catch {}
    }, 5000);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (statusIntervalRef.current) clearInterval(statusIntervalRef.current);
    };
  }, []);

  const scheduleSave = useCallback((key: string, value: number | boolean | string) => {
    setParams((prev) => ({ ...prev, [key]: value }));
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        await updateConfig({ [key]: value } as Partial<AppConfig>);
      } catch {}
    }, 500);
  }, []);

  useEffect(() => {
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, []);

  if (!loaded) return null;

  return (
    <div className="max-w-2xl space-y-8">
      {/* Fleet status — real-time */}
      {fleetStatus && (
        <section>
          <h3 className="text-[13px] font-semibold text-on-surface mb-3">
            {t("expert.fleet.status")}
          </h3>
          <div className="bg-surface-container-low border border-outline-variant/30 rounded-lg p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-outline">{t("expert.fleet.active_model")}</span>
              <span className="text-[12px] font-mono text-on-surface">{fleetStatus.current_model.id}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-outline">{t("expert.fleet.mode")}</span>
              <span className="text-[12px] text-on-surface capitalize">{fleetStatus.mode}</span>
            </div>
            {fleetStatus.swap_in_progress && (
              <div className="flex items-center gap-2 text-yellow-500 text-[11px]">
                <span className="inline-block w-2.5 h-2.5 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
                {t("expert.fleet.swapping")} {fleetStatus.swap_target_model_id}
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-outline">{t("expert.fleet.swaps_session")}</span>
              <span className="text-[12px] text-on-surface">{fleetStatus.model_swaps_session}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-outline">RAM</span>
              <span className="text-[12px] text-on-surface">
                {fleetStatus.hardware.ram_available_gb.toFixed(1)} GB / {fleetStatus.hardware.ram_total_gb.toFixed(1)} GB
              </span>
            </div>
            {fleetStatus.selection_rationale && (
              <p className="text-[10px] text-outline italic mt-1">{fleetStatus.selection_rationale}</p>
            )}
          </div>
        </section>
      )}

      {/* Configuration */}
      <section>
        <h3 className="text-[13px] font-semibold text-on-surface mb-4">
          {t("expert.fleet.config")}
        </h3>
        <div className="space-y-4">
          {FIELDS.map((f) => {
            const val = params[f.key];
            if (f.type === "bool") {
              return (
                <div key={f.key} className="flex items-center justify-between px-3 py-2 rounded bg-surface-container-low">
                  <label className="text-[12px] text-on-surface-variant font-medium">
                    {t(`expert.fleet.${f.key}`)}
                  </label>
                  <ToggleSwitch
                    enabled={!!val}
                    onChange={(v) => scheduleSave(f.key, v)}
                    size="sm"
                    ariaLabel={t(`expert.fleet.${f.key}`)}
                  />
                </div>
              );
            }
            if (f.type === "select" && f.options) {
              return (
                <div key={f.key}>
                  <label className="text-[12px] text-on-surface-variant font-medium mb-1 block">
                    {t(`expert.fleet.${f.key}`)}
                  </label>
                  <select
                    value={val as string}
                    onChange={(e) => scheduleSave(f.key, e.target.value)}
                    className="w-full py-2 px-3 rounded-[6px] text-[13px] bg-surface-container border border-outline-variant text-on-surface focus:outline-none focus:border-primary"
                  >
                    {f.options.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                </div>
              );
            }
            if (f.type === "float") {
              return (
                <div key={f.key}>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-[12px] text-on-surface-variant font-medium">
                      {t(`expert.fleet.${f.key}`)}
                    </label>
                    <span className="text-[12px] font-mono text-on-surface">
                      {Number(val).toFixed(1)} GB
                    </span>
                  </div>
                  <input
                    type="range"
                    min={f.min}
                    max={f.max}
                    step={f.step ?? 0.1}
                    value={val as number}
                    onChange={(e) => scheduleSave(f.key, parseFloat(e.target.value))}
                    className="w-full accent-primary-container h-1.5 rounded-full appearance-none cursor-pointer bg-surface-container-highest"
                  />
                </div>
              );
            }
            return (
              <div key={f.key}>
                <label className="text-[12px] text-on-surface-variant font-medium mb-1 block">
                  {t(`expert.fleet.${f.key}`)}
                </label>
                <input
                  type="number"
                  min={f.min}
                  max={f.max}
                  value={val as number}
                  onChange={(e) => scheduleSave(f.key, parseInt(e.target.value) || (f.min ?? 0))}
                  className="w-full py-1.5 px-3 rounded-[6px] text-[13px] bg-surface-container border border-outline-variant text-on-surface focus:outline-none focus:border-primary"
                />
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
