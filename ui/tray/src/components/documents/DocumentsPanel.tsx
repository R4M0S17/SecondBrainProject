import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { open } from "@tauri-apps/plugin-dialog";
import { useDocumentsStore } from "../../stores/documents";
import { useSettingsStore } from "../../stores/settings";
import { useDashboardStore } from "../../stores/dashboard";

interface DocumentsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function DocumentsPanel({ isOpen, onClose }: DocumentsPanelProps) {
  const { t } = useTranslation();
  const {
    docs, loading, error: storeError, usingCache, pendingCount,
    refresh, addDocuments, removeDocument,
  } = useDocumentsStore();
  const folders = useSettingsStore((s) => s.config?.watched_folders ?? []);
  const startIndexing = useSettingsStore((s) => s.startIndexing);
  const setSearchDocsOpen = useDashboardStore((s) => s.setSearchDocsOpen);
  const [filenameFilter, setFilenameFilter] = useState("");

  useEffect(() => {
    if (!isOpen) setFilenameFilter("");
  }, [isOpen]);

  const filteredDocs = filenameFilter
    ? docs.filter((d) => d.filename.toLowerCase().includes(filenameFilter.toLowerCase()))
    : docs;

  useEffect(() => {
    if (isOpen) void refresh();
  }, [isOpen, refresh]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleDelete = async (sourcePath: string) => {
    await removeDocument(sourcePath);
  };

  const handleReindex = () => {
    void startIndexing(folders);
  };

  const handleFileSelect = async () => {
    try {
      const selected = await open({
        multiple: true,
        title: "Select files to index",
        filters: [{
          name: t("documents.documents_filter"),
          extensions: ["pdf", "txt", "md", "py", "docx", "csv"],
        }],
      });
      if (!selected) return;
      const paths = Array.isArray(selected) ? selected : [selected];
      await addDocuments(paths);
    } catch {
      // user cancelled
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex" role="complementary" aria-label="Documents">
      <div className="flex-1 bg-black/40" onClick={onClose} aria-hidden="true" />
      <aside
        className={`w-[360px] h-full bg-surface-container border-l border-outline-variant flex flex-col z-10 transition-transform duration-200 ease-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <header className="h-[48px] flex items-center justify-between px-4 bg-surface-container border-b border-outline-variant shrink-0">
          <h2 className="text-[15px] font-semibold text-on-surface">{t("documents.title")}</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={handleReindex}
              className="p-1 rounded text-on-surface-variant hover:bg-surface-container-highest transition-colors"
              title={t("documents.reindex")}
            >
              <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M1 4v6h6M23 20v-6h-6" />
                <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15" />
              </svg>
            </button>
            <button
              onClick={handleFileSelect}
              className="p-1 rounded text-on-surface-variant hover:bg-surface-container-highest transition-colors"
              title={t("documents.upload")}
            >
              <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
              </svg>
            </button>
            <button
              onClick={onClose}
              className="p-1 rounded text-on-surface-variant hover:bg-surface-container-highest transition-colors"
              aria-label={t("documents.close")}
            >
              <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
          {storeError && (
            <div className="text-[11px] text-error bg-surface-container-low rounded p-2 mb-3">{storeError}</div>
          )}

          {usingCache && !loading && (
            <div className="flex items-center gap-1.5 mb-3 text-[10px] text-outline bg-surface-container px-2 py-1 rounded">
              <span className="w-1.5 h-1.5 rounded-full bg-outline inline-block" />
              {t("documents.offline_mode")}
              {pendingCount > 0 && ` · ${t("documents.pending_sync", { count: pendingCount })}`}
            </div>
          )}

          {/* Filename filter */}
          {!loading && docs.length > 0 && (
            <div className="mb-3 space-y-2">
              <div className="relative">
                <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-[16px] text-outline">search</span>
                <input
                  type="text"
                  value={filenameFilter}
                  onChange={(e) => setFilenameFilter(e.target.value)}
                  placeholder={t("search_docs.query_placeholder")}
                  className="w-full pl-8 pr-3 py-2 rounded-lg bg-surface-container border border-outline-variant/50 text-on-surface text-[12px] placeholder:text-outline/50 focus:outline-none focus:border-primary transition-colors"
                />
              </div>
              <button
                onClick={() => { setSearchDocsOpen(true); }}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-primary-container/10 border border-primary/20 text-[12px] text-primary hover:bg-primary-container/20 transition-colors"
              >
                <span className="material-symbols-outlined text-[16px]">psychology</span>
                {t("search_docs.title")}
              </button>
            </div>
          )}

          {loading ? (
            <div className="text-[12px] text-outline text-center py-8">{t("status.loading")}</div>
          ) : filteredDocs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center gap-3">
              <svg className="w-10 h-10 text-outline" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
              <p className="text-[12px] text-outline">{filenameFilter ? t("search_docs.no_results") : t("documents.empty")}</p>
              <p className="text-[11px] text-outline">
                {t("documents.empty_hint")}
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              <div className="text-[11px] text-outline mb-2">
                {t("documents.count", { count: filteredDocs.length })}{filenameFilter ? ` (filtered)` : ""}
              </div>
              {filteredDocs.map((doc) => (
                <div
                  key={doc.source_path}
                  className="flex items-center justify-between bg-surface-container p-2 rounded-[6px] group"
                >
                  <div className="flex items-center gap-2 overflow-hidden min-w-0">
                    <svg className="w-[16px] h-[16px] text-outline shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    <span className="font-mono text-[12px] text-on-surface truncate" title={doc.source_path}>
                      {doc.filename}
                    </span>
                  </div>
                  <button
                    onClick={() => void handleDelete(doc.source_path)}
                    className="text-on-surface-variant opacity-0 group-hover:opacity-100 transition-opacity ml-2 shrink-0"
                    aria-label={t("documents.delete_file", { filename: doc.filename })}
                  >
                    <svg className="w-[16px] h-[16px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
