import { useTranslation } from "react-i18next";
import type { Workflow } from "../../api/types";
import type { WorkflowViewTab } from "../../stores/workflows";
import WorkflowCard from "./WorkflowCard";

interface WorkflowListProps {
  workflows: Workflow[];
  selectedId: string | null;
  isLoading: boolean;
  viewTab: WorkflowViewTab;
  onSelect: (id: string) => void;
  onQuickRun?: (id: string) => void;
}

export default function WorkflowList({
  workflows,
  selectedId,
  isLoading,
  viewTab,
  onSelect,
  onQuickRun,
}: WorkflowListProps) {
  const { t } = useTranslation();
  const sectionLabel =
    viewTab === "recipes" ? t("workflows.tab_recipes") : t("workflows.tab_routines");

  return (
    <aside className="w-80 shrink-0 border-r border-outline-variant/10 overflow-y-auto scrollbar-auto bg-surface-container-low/20">
      <div className="px-4 py-2 text-label-caps text-outline tracking-wider uppercase">
        {sectionLabel}
      </div>
      {isLoading && workflows.length === 0 && (
        <div className="px-4 py-8 text-[12px] text-outline text-center">{t("workflows.loading")}</div>
      )}
      {workflows.length === 0 && !isLoading && (
        <div className="px-4 py-8 text-[12px] text-outline text-center">
          {viewTab === "recipes" ? t("workflows.no_recipes") : t("workflows.empty_title")}
        </div>
      )}
      {workflows.map((wf, i) => (
        <div key={wf.id} className={`stagger-${Math.min(i + 1, 5)}`}>
          <WorkflowCard
            workflow={wf}
            selected={selectedId === wf.id}
            onSelect={() => onSelect(wf.id)}
            onQuickRun={onQuickRun ? () => onQuickRun(wf.id) : undefined}
          />
        </div>
      ))}
    </aside>
  );
}
