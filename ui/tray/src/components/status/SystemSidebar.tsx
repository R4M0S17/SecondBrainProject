import { useState } from "react";
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

  if (collapsed) {
    return (
      <aside className={`flex flex-col items-center pt-4 w-10 border-l border-outline-variant/20 glass-panel z-40 shrink-0 ${className}`}>
        <button
          onClick={() => setCollapsed(false)}
          className="p-1.5 text-on-surface-variant hover:text-primary transition-colors rounded hover:bg-surface-container"
          aria-label="Expand sidebar"
          title="Expand sidebar"
        >
          <span className="material-symbols-outlined text-[18px]">chevron_left</span>
        </button>
      </aside>
    );
  }

  return (
    <aside className={`flex flex-col p-5 md:p-6 border-l border-outline-variant/20 glass-panel z-40 shrink-0 overflow-y-auto scrollbar-auto relative ${className}`}>
      <button
        onClick={() => setCollapsed(true)}
        className="absolute top-3 right-3 p-1 text-on-surface-variant hover:text-primary transition-colors rounded hover:bg-surface-container"
        aria-label="Collapse sidebar"
        title="Collapse sidebar"
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
