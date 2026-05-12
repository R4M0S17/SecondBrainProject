import type { SourceRef } from "../../api/types";

interface SourcesPanelProps {
  sources: SourceRef[];
}

export default function SourcesPanel({ sources }: SourcesPanelProps) {
  if (sources.length === 0) return null;

  return (
    <div className="bg-[#1c1b23] border-l-2 border-[#6b7a90] p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold tracking-[0.05em] uppercase text-[#c9c4d7]">
          SOURCES
        </span>
      </div>
      <div className="space-y-1">
        {sources.map((src, i) => (
          <div
            key={i}
            className="flex items-center justify-between group cursor-pointer"
          >
            <span
              className={`font-mono text-[11px] truncate max-w-[200px] ${
                i === 0 ? "text-[#94a3b8]" : "text-[#c9c4d7]"
              }`}
              title={src.path}
            >
              {src.path}
            </span>
            <div className="flex items-center gap-2 shrink-0">
              <div className="w-16 h-[2px] bg-[#242736] overflow-hidden">
                <div
                  className={`h-full ${i === 0 ? "bg-[#94a3b8]" : "bg-[#94a3b8] opacity-60"}`}
                  style={{ width: `${Math.round(src.score * 100)}%` }}
                />
              </div>
              <span className="font-mono text-[10px] text-[#c9c4d7]">
                {src.score.toFixed(2)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
