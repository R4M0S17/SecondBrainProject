export default function CpuMiniGraph() {
  const cpuAvg = 0;

  return (
    <div className="bg-surface-container/40 rounded-xl p-5 border border-outline-variant/20 mb-6 hover:bg-surface-container/60 transition-colors">
      <div className="flex justify-between items-start mb-3">
        <span className="text-xs font-medium text-on-surface-variant">Compute Load</span>
        <span className="material-symbols-outlined text-[16px] text-primary-container">speed</span>
      </div>
      <div className="flex items-end gap-3 mb-2">
        <span className="font-label-mono text-2xl text-on-surface">
          {cpuAvg > 0 ? Math.round(cpuAvg) : "—"}
        </span>
        <span className="text-xs text-outline mb-1">{cpuAvg > 0 ? "% AVG" : ""}</span>
      </div>
      <div className="h-8 flex items-end gap-1 w-full mt-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="w-1/6 rounded-t-sm bg-surface-variant/30" style={{ height: "10%" }} />
        ))}
      </div>
    </div>
  );
}
