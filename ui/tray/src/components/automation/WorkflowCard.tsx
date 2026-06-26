import { useTranslation } from "react-i18next";
import type { Workflow } from "../../api/types";
import { formatRelativeTime } from "../../utils/time";

interface WorkflowCardProps {
  workflow: Workflow;
  selected: boolean;
  onSelect: () => void;
  onQuickRun?: () => void;
}

export default function WorkflowCard({
  workflow,
  selected,
  onSelect,
  onQuickRun,
}: WorkflowCardProps) {
  const { t } = useTranslation();
  const icon = workflow.workflow_type === "recipe" ? "smart_toy" : "desktop_mac";

  return (
    <div
      className={`group relative border-b border-outline-variant/10 transition-all duration-200 hover:bg-surface-container/60 ${
        selected ? "bg-surface-container/80" : ""
      }`}
    >
      <button type="button" onClick={onSelect} className="w-full text-left px-4 py-3 active:scale-[0.99]">
        <div className="flex items-start gap-3">
          <span className="material-symbols-outlined text-[20px] text-primary-container/80 mt-0.5 shrink-0">
            {icon}
          </span>
          <div className="min-w-0 flex-1 pr-8">
            <div className="truncate text-[13px] font-medium text-on-surface">{workflow.name}</div>
            <div className="flex flex-wrap gap-x-2 gap-y-0.5 mt-1 text-[11px] text-outline">
              <span>{t("workflows.list_runs", { count: workflow.run_count })}</span>
              {workflow.last_run != null && (
                <span>
                  · {formatRelativeTime(new Date(workflow.last_run * 1000))}
                </span>
              )}
            </div>
          </div>
        </div>
      </button>
      {onQuickRun && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onQuickRun();
          }}
          className="absolute right-3 top-1/2 -translate-y-1/2 w-8 h-8 rounded-lg bg-[#22c55e]/20 text-success-green
                     opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center
                     hover:bg-[#22c55e]/30 active:scale-95"
          title={t("workflows.run")}
        >
          <span className="material-symbols-outlined text-[18px]">play_arrow</span>
        </button>
      )}
    </div>
  );
}
