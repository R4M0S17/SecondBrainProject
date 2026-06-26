import { useRef } from "react";
import { useTranslation } from "react-i18next";

interface WorkflowHeaderProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  onRecordStart: () => void;
  onImport?: (file: File) => void;
  isRecording: boolean;
  isGeneralizing: boolean;
}

export default function WorkflowHeader({
  searchQuery,
  onSearchChange,
  onRecordStart,
  onImport,
  isRecording,
  isGeneralizing,
}: WorkflowHeaderProps) {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <header className="shrink-0 px-6 md:px-10 pt-6 pb-4 border-b border-outline-variant/10">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-display-lg text-on-surface select-none">{t("workflows.title")}</h1>
          <p className="text-body-base text-on-surface-variant/70 mt-1 select-none">
            {t("workflows.subtitle")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={t("workflows.search_placeholder")}
            className="w-full sm:w-56 px-3 py-2 text-[13px] rounded-xl bg-surface-container-low/40 border border-outline-variant/10 text-on-surface placeholder:text-outline focus:outline-none focus:border-primary-container/50"
          />
          {onImport && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) onImport(file);
                  e.target.value = "";
                }}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isRecording || isGeneralizing}
                className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-container-low/60 text-on-surface-variant text-[13px] shrink-0 hover:bg-surface-container/60 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                title={t("workflows.import")}
              >
                <span className="material-symbols-outlined text-[18px]">upload</span>
                <span className="hidden sm:inline">{t("workflows.import")}</span>
              </button>
            </>
          )}
          <button
            type="button"
            onClick={onRecordStart}
            disabled={isRecording || isGeneralizing}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary-container text-on-primary-container text-[13px] font-medium shrink-0 hover:opacity-90 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            <span className="material-symbols-outlined text-[18px]">fiber_manual_record</span>
            {t("workflows.record_start")}
          </button>
        </div>
      </div>
    </header>
  );
}
