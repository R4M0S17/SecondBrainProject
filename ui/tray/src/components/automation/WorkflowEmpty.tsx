import { useTranslation } from "react-i18next";
import ActionCard from "../dashboard/ActionCard";

import type { WorkflowViewTab } from "../../stores/workflows";

interface WorkflowEmptyProps {
  variant: WorkflowViewTab;
  onRecordStart: () => void;
  onOpenTemplates: () => void;
  onInstallTemplate: (templateId: string) => void;
}

export default function WorkflowEmpty({
  variant,
  onRecordStart,
  onOpenTemplates,
  onInstallTemplate,
}: WorkflowEmptyProps) {
  const { t } = useTranslation();
  const isRecipes = variant === "recipes";

  return (
    <div className="flex flex-col items-center justify-center flex-1 px-6 py-16 text-center dashboard-enter">
      <span className="material-symbols-outlined text-[48px] text-primary-container/80 mb-4 stagger-1">
        {isRecipes ? "smart_toy" : "account_tree"}
      </span>
      <h2 className="text-[20px] font-semibold text-on-surface mb-2 stagger-2">
        {isRecipes ? t("workflows.no_recipes") : t("workflows.empty_title")}
      </h2>
      <p className="text-[14px] text-on-surface-variant/70 max-w-md mb-10 stagger-3">
        {isRecipes ? t("workflows.no_recipes_hint") : t("workflows.empty_subtitle")}
      </p>
      {!isRecipes && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-2xl stagger-4">
            <ActionCard
              icon="fiber_manual_record"
              label={t("workflows.empty_record_cta")}
              description={t("workflows.subtitle")}
              onClick={onRecordStart}
            />
            <ActionCard
              icon="calendar_month"
              label={t("workflows.template_calendar")}
              description={t("workflows.template_calendar_desc")}
              onClick={() => onInstallTemplate("recipe-calendar-week-md")}
            />
            <ActionCard
              icon="folder_open"
              label={t("workflows.template_files")}
              description={t("workflows.template_files_desc")}
              onClick={() => onInstallTemplate("recipe-search-pdfs-desktop")}
            />
          </div>
          <button
            type="button"
            onClick={onOpenTemplates}
            className="mt-6 text-[13px] text-primary-container hover:underline stagger-5"
          >
            {t("workflows.browse_templates")}
          </button>
        </>
      )}
      {isRecipes && (
        <button
          type="button"
          onClick={onOpenTemplates}
          className="text-[13px] px-4 py-2 rounded-xl bg-primary-container text-on-primary-container font-medium hover:opacity-90 stagger-4"
        >
          {t("workflows.browse_templates")}
        </button>
      )}
    </div>
  );
}
