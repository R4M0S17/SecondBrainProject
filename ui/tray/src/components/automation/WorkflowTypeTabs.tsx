import { useTranslation } from "react-i18next";
import type { WorkflowViewTab } from "../../stores/workflows";

interface WorkflowTypeTabsProps {
  active: WorkflowViewTab;
  onChange: (tab: WorkflowViewTab) => void;
}

export default function WorkflowTypeTabs({ active, onChange }: WorkflowTypeTabsProps) {
  const { t } = useTranslation();
  const tabs: { id: WorkflowViewTab; label: string }[] = [
    { id: "routines", label: t("workflows.tab_routines") },
    { id: "recipes", label: t("workflows.tab_recipes") },
    { id: "templates", label: t("workflows.tab_templates") },
  ];

  return (
    <nav className="flex gap-1 px-6 md:px-10 py-3 border-b border-outline-variant/10 shrink-0">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={`px-3 py-1.5 text-[12px] font-medium rounded-lg transition-colors ${
            active === tab.id
              ? "bg-surface-container text-on-surface"
              : "text-outline hover:text-on-surface-variant hover:bg-surface-container-low/50"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
