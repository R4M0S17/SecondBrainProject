import { useTranslation } from "react-i18next";
import type { MemoryRef } from "../../api/types";

interface MemoryPanelProps {
  memory: MemoryRef[];
  onViewAll?: () => void;
}

export default function MemoryPanel({ memory, onViewAll }: MemoryPanelProps) {
  const { t } = useTranslation();
  if (memory.length === 0) return null;

  return (
    <div className="bg-violet-500/5 border border-violet-400/15 rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="material-symbols-outlined text-[14px] text-violet-400/70">neurology</span>
          <span className="text-[10px] font-semibold tracking-[0.06em] uppercase text-violet-400/70">
            {t("memory.used_in_response", { count: memory.length })}
          </span>
        </div>
        {onViewAll && (
          <button
            type="button"
            onClick={onViewAll}
            className="text-[10px] text-violet-400/60 hover:text-violet-400 transition-colors underline"
          >
            {t("memory.view_all")}
          </button>
        )}
      </div>
      <div className="space-y-1.5">
        {memory.map((mem) => (
          <div key={mem.id} className="space-y-0.5">
            <p className="text-[11px] text-on-surface-variant/80 leading-[15px] line-clamp-2 italic">
              &ldquo;{mem.summary_snippet}&rdquo;
            </p>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-[2px] bg-surface-container overflow-hidden rounded-full">
                <div
                  className="h-full bg-violet-400/60 rounded-full"
                  style={{ width: `${Math.round(mem.relevance_score * 100)}%` }}
                />
              </div>
              <span className="font-mono text-[9px] text-outline">
                {mem.relevance_score.toFixed(2)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
