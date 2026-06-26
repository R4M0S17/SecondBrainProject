import { useTranslation } from "react-i18next";
import ActionCard from "../dashboard/ActionCard";
import type { WorkflowRecipe } from "../../api/types";

interface RecipeTemplateGridProps {
  templates: WorkflowRecipe[];
  templatesLoaded: boolean;
  onInstall: (templateId: string) => void;
  installingId: string | null;
}

const TEMPLATE_ICONS: Record<string, string> = {
  "recipe-calendar-week-md": "calendar_month",
  "recipe-search-pdfs-desktop": "folder_open",
  "recipe-reminder": "notifications",
};

export default function RecipeTemplateGrid({
  templates,
  templatesLoaded,
  onInstall,
  installingId,
}: RecipeTemplateGridProps) {
  const { t } = useTranslation();

  if (!templatesLoaded) {
    return (
      <div className="flex items-center justify-center flex-1 text-[13px] text-outline">
        {t("workflows.loading")}
      </div>
    );
  }

  if (templates.length === 0) {
    return (
      <div className="flex items-center justify-center flex-1 text-[13px] text-outline px-6 text-center">
        {t("workflows.templates_unavailable")}
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 md:px-10 py-8">
      <h2 className="text-[18px] font-semibold text-on-surface mb-2">
        {t("workflows.tab_templates")}
      </h2>
      <p className="text-[13px] text-on-surface-variant/70 mb-6">{t("workflows.templates_subtitle")}</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 max-w-4xl">
        {templates.map((tmpl) => (
          <ActionCard
            key={tmpl.id}
            icon={TEMPLATE_ICONS[tmpl.id] ?? "smart_toy"}
            label={tmpl.name}
            description={tmpl.description}
            onClick={() => onInstall(tmpl.id)}
            disabled={installingId === tmpl.id}
            disabledReason={t("workflows.installing")}
          />
        ))}
      </div>
    </div>
  );
}
