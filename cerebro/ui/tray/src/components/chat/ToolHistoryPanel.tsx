import type { ToolCallRecord } from "../../api/types";

interface ToolHistoryPanelProps {
  tools: ToolCallRecord[];
}

export default function ToolHistoryPanel({ tools }: ToolHistoryPanelProps) {
  if (tools.length === 0) return null;

  return (
    <div className="bg-[#1c1b23] border border-[#242736] rounded-sm overflow-hidden">
      <div className="bg-[#35343d] px-3 py-1 border-b border-[#242736] flex items-center justify-between">
        <span className="text-[10px] font-bold tracking-[0.05em] uppercase text-[#c9c4d7]">
          TOOLS CALLED
        </span>
      </div>
      <div className="p-1 space-y-[1px]">
        {tools.map((tool, i) => (
          <div
            key={i}
            className="flex items-center justify-between px-2 py-2 bg-[#1c1b23] hover:bg-[#201f27] transition-colors"
          >
            <div className="flex items-center gap-2">
              {tool.approved ? (
                <svg
                  className="w-4 h-4 text-[#4ade80]"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                </svg>
              ) : (
                <svg
                  className="w-4 h-4 text-[#ffb4ab]"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
                </svg>
              )}
              <span className="font-mono text-[12px] text-[#e5e0ed]">
                {tool.name}
              </span>
            </div>
            <span className="font-mono text-[10px] text-[#c9c4d7] opacity-60">
              {(tool.latency_ms / 1000).toFixed(1)}s
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
