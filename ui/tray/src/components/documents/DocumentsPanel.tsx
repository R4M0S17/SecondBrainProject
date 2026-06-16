import { useCallback, useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { listDocuments, deleteDocument, startIndex } from "../../api/client";
import type { DocumentInfo } from "../../api/types";
import { useSettingsStore } from "../../stores/settings";

interface DocumentsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function DocumentsPanel({ isOpen, onClose }: DocumentsPanelProps) {
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const folders = useSettingsStore((s) => s.config?.watched_folders ?? []);
  const startIndexing = useSettingsStore((s) => s.startIndexing);

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listDocuments();
      setDocs(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) void fetchDocs();
  }, [isOpen, fetchDocs]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleDelete = async (sourcePath: string) => {
    try {
      await deleteDocument(sourcePath);
      setDocs((prev) => prev.filter((d) => d.source_path !== sourcePath));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
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
          name: "Documents",
          extensions: ["pdf", "txt", "md", "py", "docx", "csv"],
        }],
      });
      if (!selected) return;
      const paths = Array.isArray(selected) ? selected : [selected];
      await startIndex(paths);
      void fetchDocs();
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
          <h2 className="text-[15px] font-semibold text-on-surface">Documents</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={handleReindex}
              className="p-1 rounded text-on-surface-variant hover:bg-surface-container-highest transition-colors"
              title="Re-index watched folders"
            >
              <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M1 4v6h6M23 20v-6h-6" />
                <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15" />
              </svg>
            </button>
            <button
              onClick={handleFileSelect}
              className="p-1 rounded text-on-surface-variant hover:bg-surface-container-highest transition-colors"
              title="Upload file"
            >
              <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
              </svg>
            </button>
            <button
              onClick={onClose}
              className="p-1 rounded text-on-surface-variant hover:bg-surface-container-highest transition-colors"
              aria-label="Close documents"
            >
              <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
          {error && (
            <div className="text-[11px] text-error bg-surface-container-low rounded p-2 mb-3">{error}</div>
          )}

          {loading ? (
            <div className="text-[12px] text-outline text-center py-8">Loading…</div>
          ) : docs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center gap-3">
              <svg className="w-10 h-10 text-outline" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
              <p className="text-[12px] text-outline">No indexed documents</p>
              <p className="text-[11px] text-outline">
                Add folders in Settings or upload files above
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              <div className="text-[11px] text-outline mb-2">
                {docs.length} file{docs.length !== 1 ? "s" : ""} indexed
              </div>
              {docs.map((doc) => (
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
                    aria-label={`Delete ${doc.filename}`}
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
