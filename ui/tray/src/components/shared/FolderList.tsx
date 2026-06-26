import { useTranslation } from "react-i18next";

interface FolderListProps {
  folders: string[];
  onAdd: () => void;
  onRemove: (folder: string) => void;
  minFoldersMessage?: string;
}

export default function FolderList({
  folders,
  onAdd,
  onRemove,
  minFoldersMessage,
}: FolderListProps) {
  const { t } = useTranslation();
  return (
    <div className="w-full space-y-1">
      {folders.map((folder) => (
        <div
          key={folder}
          className="flex items-center justify-between bg-surface-container p-2 rounded-[6px] group"
        >
          <div className="flex items-center gap-2 overflow-hidden">
            <svg className="w-[18px] h-[18px] text-outline shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
            </svg>
            <span className="font-mono text-[13px] text-on-surface truncate">{folder}</span>
          </div>
          <button
            onClick={() => onRemove(folder)}
            className="text-on-surface-variant opacity-0 group-hover:opacity-100 transition-opacity ml-2 shrink-0"
            aria-label={t("documents.remove_folder", { folder })}
          >
            <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}

      <button
        onClick={onAdd}
        className="w-full py-2 border border-dashed border-outline-variant rounded-[6px] text-[12px] text-outline hover:bg-surface-container-highest transition-colors flex items-center justify-center gap-1"
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M12 5v14M5 12h14" />
        </svg>
        {t("documents.add_folder")}
      </button>

      {folders.length === 0 && minFoldersMessage && (
        <p className="text-[11px] text-outline text-center">{minFoldersMessage}</p>
      )}
    </div>
  );
}
