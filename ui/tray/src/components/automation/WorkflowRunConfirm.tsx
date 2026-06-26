import { useTranslation } from "react-i18next";
import type { Workflow } from "../../api/types";

interface WorkflowRunConfirmProps {
  workflow: Workflow;
  dryRun: boolean;
  onDryRunChange: (value: boolean) => void;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function WorkflowRunConfirm({
  workflow,
  dryRun,
  onDryRunChange,
  onConfirm,
  onCancel,
}: WorkflowRunConfirmProps) {
  const { t } = useTranslation();

  return (
    <dialog
      className="fixed inset-0 bg-black/60 backdrop-blur-[4px] z-[70] flex items-center justify-center p-6"
      aria-modal="true"
      open
    >
      <div className="w-full max-w-md bg-surface-container rounded-xl border border-outline-variant shadow-2xl overflow-hidden">
        <div className="p-5 space-y-4">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-[22px] text-tertiary-fixed-dim">
              {dryRun ? "visibility" : "play_arrow"}
            </span>
            <span className="text-on-surface text-[15px] font-semibold">
              {dryRun ? t("workflows.dry_run_title") : t("workflows.run_confirm_title")}
            </span>
          </div>
          <p className="text-[13px] text-on-surface-variant">{workflow.name}</p>
          {workflow.steps.length > 0 && (
            <ol className="text-[12px] text-outline space-y-1 max-h-32 overflow-y-auto">
              {workflow.steps.map((s) => (
                <li key={s.order}>
                  {s.order}. {s.action}
                  {s.app ? ` · ${s.app}` : ""}
                </li>
              ))}
            </ol>
          )}
          <label className="flex items-center gap-2 text-[12px] text-on-surface-variant cursor-pointer">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => onDryRunChange(e.target.checked)}
              className="rounded border-outline-variant"
            />
            {t("workflows.dry_run_label")}
          </label>
          {!dryRun && (
            <p className="text-[12px] text-outline leading-relaxed">
              {workflow.workflow_type === "recipe"
                ? t("workflows.run_confirm_recipe")
                : t("workflows.run_confirm_desktop")}
            </p>
          )}
        </div>
        <div className="flex gap-3 px-5 pb-5">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 h-10 rounded-lg border border-outline-variant text-on-surface-variant text-sm font-medium hover:bg-surface-container-high transition-colors"
          >
            {t("workflows.record_cancel")}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="flex-1 h-10 rounded-lg bg-primary-container text-on-primary-container text-sm font-semibold hover:brightness-110 transition-all flex items-center justify-center gap-1.5"
          >
            <span className="material-symbols-outlined text-[18px]">
              {dryRun ? "visibility" : "play_arrow"}
            </span>
            {dryRun ? t("workflows.dry_run") : t("workflows.run")}
          </button>
        </div>
      </div>
    </dialog>
  );
}
