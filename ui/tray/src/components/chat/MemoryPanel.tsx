import type { MemoryRef } from "../../api/types";

interface MemoryPanelProps {
  memory: MemoryRef[];
}

export default function MemoryPanel({ memory }: MemoryPanelProps) {
  if (memory.length === 0) return null;

  return (
    <div className="bg-surface-container-low border-l-2 border-primary-fixed-dim p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
          MEMORY
        </span>
      </div>
      <div className="space-y-2">
        {memory.map((mem, i) => (
          <div key={i} className="space-y-1">
            <p className="text-[12px] text-on-surface-variant leading-[16px] line-clamp-2">
              {mem.summary_snippet}
            </p>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-[2px] bg-surface-container overflow-hidden">
                <div
                  className="h-full bg-primary-container opacity-60"
                  style={{ width: `${Math.round(mem.relevance_score * 100)}%` }}
                />
              </div>
              <span className="font-mono text-[10px] text-on-surface-variant">
                {mem.relevance_score.toFixed(2)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
