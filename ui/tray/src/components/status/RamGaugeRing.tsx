import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useSystemStore } from "../../stores/system";

export default function RamGaugeRing() {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(false);
  const status = useSystemStore((s) => s.status);

  if (!status) {
    return (
      <div className="bg-surface-container/40 rounded-xl p-5 border border-outline-variant/20 mb-4">
        <div className="flex justify-between items-start mb-4">
          <span className="text-xs font-medium text-on-surface-variant">{t("status.memory_allocation")}</span>
          <span className="material-symbols-outlined text-[16px] text-outline/40">memory</span>
        </div>
        <div className="flex justify-center py-6">
          <div className="text-[11px] text-outline/40 animate-pulse">{t("status.connecting")}</div>
        </div>
      </div>
    );
  }

  const usedGb = status.ram_used_gb ?? 0;
  const totalGb = status.ram_total_gb ?? (usedGb + (status.ram_available_gb ?? 0));
  const percent = totalGb > 0 ? (usedGb / totalGb) * 100 : 0;
  const circumference = 2 * Math.PI * 40;
  const dashOffset = circumference - (percent / 100) * circumference;
  const isPressed = percent > 80;

  return (
    <div className="bg-surface-container/40 rounded-xl p-5 border border-outline-variant/20 mb-4 relative overflow-hidden group hover:bg-surface-container/60 transition-colors">
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex justify-between items-start mb-4 text-left"
      >
        <span className="text-xs font-medium text-on-surface-variant">{t("status.memory_allocation")}</span>
        <div className="flex items-center gap-2">
          {collapsed && (
            <span className="text-xs font-label-mono text-primary-container tabular-nums">
              {Math.round(percent)}%
            </span>
          )}
          <span className={`material-symbols-outlined text-[16px] text-primary-container transition-transform ${collapsed ? "" : "rotate-180"}`}>
            expand_less
          </span>
        </div>
      </button>

      {!collapsed && (
        <>
          <div className="flex justify-center items-center py-2">
            <div className="relative w-32 h-32 flex items-center justify-center">
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                <circle
                  cx="50" cy="50" r="40"
                  fill="none"
                  stroke="rgba(255,255,255,0.05)"
                  strokeWidth="6"
                />
                <circle
                  cx="50" cy="50" r="40"
                  fill="none"
                  stroke="#2563eb"
                  strokeWidth="6"
                  strokeDasharray={circumference}
                  strokeDashoffset={dashOffset}
                  strokeLinecap="round"
                  className="transition-all duration-1000 ease-out"
                  style={{ filter: "drop-shadow(0 0 4px rgba(37,99,235,0.5))" }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="font-label-mono text-lg font-bold text-primary-container">
                  {usedGb.toFixed(2)}
                </span>
                <span className="text-[10px] text-outline uppercase">
                  {t("status.gb_of", { total: totalGb.toFixed(1) })}
                </span>
              </div>
            </div>
          </div>
          <div className="mt-2 text-center text-[10px] text-on-surface-variant font-label-mono">
            {t("status.utilized", { percent: Math.round(percent) })}
            {isPressed && <span className="text-[10px] text-error font-semibold"> • {t("status.high_pressure")}</span>}
          </div>
        </>
      )}
    </div>
  );
}
