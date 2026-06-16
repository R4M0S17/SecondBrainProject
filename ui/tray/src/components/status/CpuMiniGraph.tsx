import { useEffect, useRef } from "react";
import { useSystemStore } from "../../stores/system";

const HISTORY_LEN = 12;

export default function CpuMiniGraph() {
  const cpuPercent = useSystemStore((s) => s.status?.cpu_percent ?? 0);
  const historyRef = useRef<number[]>([]);

  useEffect(() => {
    const h = historyRef.current;
    h.push(cpuPercent);
    if (h.length > HISTORY_LEN) h.shift();
  }, [cpuPercent]);

  const displayVal = cpuPercent > 0 ? cpuPercent : null;
  const history = historyRef.current;
  const maxH = Math.max(...history, 1);

  return (
    <div className="bg-surface-container/40 rounded-xl p-5 border border-outline-variant/20 mb-6 hover:bg-surface-container/60 transition-colors">
      <div className="flex justify-between items-start mb-3">
        <span className="text-xs font-medium text-on-surface-variant">Compute Load</span>
        <span className="material-symbols-outlined text-[16px] text-primary-container">speed</span>
      </div>
      <div className="flex items-end gap-3 mb-2">
        <span className="font-label-mono text-2xl text-on-surface">
          {displayVal !== null ? Math.round(displayVal) : "—"}
        </span>
        <span className="text-xs text-outline mb-1">{displayVal !== null ? "%" : ""}</span>
      </div>
      <div className="h-8 flex items-end gap-1 w-full mt-2">
        {history.map((val, i) => (
          <div
            key={i}
            className="w-1/6 rounded-t-sm bg-surface-variant/30 transition-all"
            style={{ height: `${(val / maxH) * 100}%`, minHeight: val > 0 ? "4px" : "0" }}
          />
        ))}
      </div>
    </div>
  );
}
