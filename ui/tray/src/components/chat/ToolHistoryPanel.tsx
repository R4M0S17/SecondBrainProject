import type { ToolCallRecord } from "../../api/types";

interface ToolHistoryPanelProps {
  tools: ToolCallRecord[];
}

export default function ToolHistoryPanel({ tools }: ToolHistoryPanelProps) {
  if (tools.length === 0) return null;

  return (
    <div className="bg-surface-container-low border border-outline-variant rounded-sm overflow-hidden">
      <div className="bg-surface-container-highest px-3 py-1 border-b border-outline-variant flex items-center justify-between">
        <span className="text-[10px] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
          TOOLS CALLED
        </span>
      </div>
      <div className="p-1 space-y-[1px]">
        {tools.map((tool, i) => (
          <div
            key={i}
            className="flex items-center justify-between px-2 py-2 bg-surface-container-low hover:bg-surface-container transition-colors"
          >
            <div className="flex items-center gap-2">
              {tool.approved ? (
                <span className="material-symbols-outlined text-[16px] text-success-green">check_circle</span>
              ) : (
                <span className="material-symbols-outlined text-[16px] text-error">error</span>
              )}
              <span className="font-mono text-[12px] text-on-surface">
                {tool.name}
              </span>
            </div>
            <span className="font-mono text-[10px] text-on-surface-variant opacity-60">
              {(tool.latency_ms / 1000).toFixed(1)}s
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
