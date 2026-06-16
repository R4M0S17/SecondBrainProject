import { useState } from "react";
import { useSystemStore } from "../../stores/system";
import RamGaugeRing from "./RamGaugeRing";
import CpuMiniGraph from "./CpuMiniGraph";
import StorageAccessButton from "./StorageAccessButton";
import ActiveFleetList from "./ActiveFleetList";

interface SystemSidebarProps {
  className?: string;
  onOpenDocuments?: () => void;
}

export default function SystemSidebar({ className = "", onOpenDocuments }: SystemSidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const status = useSystemStore((s) => s.status);
  const usedGb = status?.ram_used_gb ?? 0;
  const totalGb = status?.ram_total_gb ?? (usedGb + (status?.ram_available_gb ?? 1));
  const ramPercent = totalGb > 0 ? (usedGb / totalGb) * 100 : 0;

  const ramColor =
    ramPercent > 80 ? "#ef4444" :
    ramPercent > 60 ? "#f59e0b" :
    "#22c55e";

  if (collapsed) {
    return (
      <aside className={`flex flex-col items-center pt-4 w-10 border-l border-outline-variant/20 glass-panel z-40 shrink-0 ${className}`}>
        <button
          onClick={() => setCollapsed(false)}
          className="p-1.5 text-on-surface-variant hover:text-primary-container transition-colors rounded hover:bg-surface-container"
          aria-label="Expand Fleet panel"
          title="Fleet"
        >
          <span className="material-symbols-outlined text-[20px]">dns</span>
        </button>
        <div className="mt-auto mb-4 flex flex-col items-center gap-1">
          <svg className="w-6 h-6" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="2.5" />
            <circle
              cx="12" cy="12" r="10"
              fill="none"
              stroke={ramColor}
              strokeWidth="2.5"
              strokeDasharray={2 * Math.PI * 10}
              strokeDashoffset={2 * Math.PI * 10 * (1 - ramPercent / 100)}
              strokeLinecap="round"
              className="transition-all duration-1000 ease-out"
              transform="rotate(-90 12 12)"
            />
          </svg>
          <span className="text-[8px] font-label-mono tabular-nums text-on-surface-variant">{Math.round(ramPercent)}%</span>
        </div>
      </aside>
    );
  }

  return (
    <aside className={`flex flex-col p-5 md:p-6 border-l border-outline-variant/20 glass-panel z-40 shrink-0 overflow-y-auto scrollbar-auto relative min-h-0 ${className}`}>
      <button
        onClick={() => setCollapsed(true)}
        className="absolute top-3 right-3 p-1 text-on-surface-variant hover:text-primary-container transition-colors rounded hover:bg-surface-container"
        aria-label="Collapse Fleet panel"
        title="Collapse Fleet panel"
      >
        <span className="material-symbols-outlined text-[16px]">chevron_right</span>
      </button>
      <div className="mb-6">
        <h2 className="text-sm font-semibold tracking-wider text-on-surface-variant uppercase mb-5">
          System Status
        </h2>
        <RamGaugeRing />
        <CpuMiniGraph />
        <StorageAccessButton onOpen={onOpenDocuments} />
      </div>
      <ActiveFleetList />
    </aside>
  );
}
