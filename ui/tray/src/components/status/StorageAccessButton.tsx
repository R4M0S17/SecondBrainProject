import { useTranslation } from "react-i18next";
import { useSystemStore } from "../../stores/system";

interface StorageAccessButtonProps {
  onOpen?: () => void;
}

export default function StorageAccessButton({ onOpen }: StorageAccessButtonProps) {
  const { t } = useTranslation();
  const status = useSystemStore((s) => s.status);
  const files = status?.indexed_files ?? 0;

  return (
    <button
      onClick={onOpen}
      className="w-full bg-surface-container/40 rounded-xl p-4 border border-outline-variant/20 mb-6 hover:bg-surface-container/60 transition-colors flex items-center justify-between group"
    >
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-primary-container/10 text-primary-container flex items-center justify-center border border-primary-container/20 group-hover:bg-primary-container/20 transition-colors">
          <span className="material-symbols-outlined text-[18px]">folder</span>
        </div>
        <div className="flex flex-col items-start">
          <span className="text-xs font-medium text-on-surface-variant uppercase tracking-wider mb-0.5">
            {t("documents.storage_access")}
          </span>
          <span className="text-sm font-medium text-on-surface">
            {!status
              ? t("status.connecting")
              : files > 0
                ? t("documents.file_count", { count: files })
                : t("documents.file_count", { count: 0 })}
          </span>
        </div>
      </div>
      <span className="material-symbols-outlined text-[20px] text-on-surface-variant group-hover:text-on-surface transition-colors">
        chevron_right
      </span>
    </button>
  );
}
