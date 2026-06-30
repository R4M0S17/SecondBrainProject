import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useSettingsStore } from "../../stores/settings";
import { useSystemStore } from "../../stores/system";
import { useChatStore } from "../../stores/chat";
import { useTabStore } from "../../stores/tab";
import { useDashboardStore } from "../../stores/dashboard";
import { searchDocuments, writeQuickNote } from "../../api/client";
import { buildDocumentSearchPrompt } from "../../utils/documentSearchPrompt";
import Dialog from "../shared/Dialog";
import type { DocumentSearchResponse } from "../../api/types";

interface SearchDocumentsDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onDocumentsOpen?: () => void;
}

type Screen = "search" | "loading" | "results" | "error";

export default function SearchDocumentsDialog({ isOpen, onClose, onDocumentsOpen }: SearchDocumentsDialogProps) {
  const { t, i18n } = useTranslation();
  const config = useSettingsStore((s) => s.config);
  const engineOk = useSystemStore((s) => s.status?.engine_ok ?? false);
  const watchedFolders = config?.watched_folders ?? [];
  const setPendingChatAction = useChatStore((s) => s.setPendingChatAction);
  const setTab = useTabStore((s) => s.setTab);
  const pushActivity = useDashboardStore((s) => s.pushActivity);

  const inputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"chunks" | "answer">("chunks");
  const [sourcePrefix, setSourcePrefix] = useState<string | null>(null);
  const [screen, setScreen] = useState<Screen>("search");
  const [result, setResult] = useState<DocumentSearchResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setMode("chunks");
      setSourcePrefix(null);
      setScreen("search");
      setResult(null);
      setErrorMsg("");
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const canSearch = query.trim().length >= 2;

  const handleSearch = async () => {
    if (!canSearch) return;
    setScreen("loading");

    try {
      const res = await searchDocuments({
        query: query.trim(),
        mode,
        top_k: 8,
        source_prefix: sourcePrefix,
      });
      setResult(res);
      setScreen("results");
      pushActivity({
        label: t("search_docs.activity", { query: query.trim().slice(0, 60) }),
        description: t("search_docs.activity_desc", { count: res.hits.length }),
        icon: "search",
        tab: "home",
      });
    } catch {
      setErrorMsg(t("search_docs.error_occurred"));
      setScreen("error");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && canSearch) {
      handleSearch();
    }
  };

  const handleDeepDive = () => {
    if (!result) return;
    const query = buildDocumentSearchPrompt(
      result.query,
      result.hits,
      i18n.language,
      t,
      result.answer,
    );
    setPendingChatAction({ query, autoSend: true, agentId: "auto" });
    setTab("chat");
    onClose();
  };

  const handleDiskSearch = () => {
    if (!query.trim()) return;
    const q = `Busca archivos que contengan "${query.trim()}" en mis carpetas autorizadas`;
    setPendingChatAction({ query: q, autoSend: true });
    setTab("chat");
    onClose();
  };

  const handleSaveNote = async () => {
    if (!result) return;
    const lines = [
      `# Búsqueda en documentos: ${result.query}`,
      `Generado: ${new Date().toISOString()}`,
      `Modo: ${result.mode} · ${result.hits.length} resultados · ${result.latency_ms} ms`,
      "",
    ];
    if (result.answer) {
      lines.push("## Respuesta", result.answer, "");
    }
    lines.push("## Fragmentos");
    for (const h of result.hits) {
      lines.push(`### ${h.filename} (chunk ${h.chunk_index})`, `> ${h.snippet}`, `*Score: ${h.score.toFixed(4)}*`, "");
    }
    try {
      await writeQuickNote(lines.join("\n"), `search-${result.query.replace(/[^a-zA-Z0-9]/g, "-").slice(0, 40)}`);
    } catch {
      // silent
    }
  };

  const searchScreen = (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-on-surface">{t("search_docs.title")}</h3>
      <p className="text-sm text-on-surface-variant">{t("search_docs.subtitle")}</p>

      <div>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("search_docs.query_placeholder")}
          className="w-full px-4 py-3 rounded-xl bg-surface-container border border-outline-variant/50 text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:border-primary transition-colors"
        />
      </div>

      <div>
        <p className="text-sm font-medium text-on-surface mb-2">{t("search_docs.mode_label")}</p>
        <div className="flex gap-2">
          {(["chunks", "answer"] as const).map((m) => {
            const disabled = m === "answer" && !engineOk;
            return (
              <button
                key={m}
                onClick={() => setMode(m)}
                disabled={disabled}
                className={`flex-1 px-4 py-2 rounded-xl text-sm border transition-colors ${
                  mode === m
                    ? "bg-primary-container/20 border-primary text-primary"
                    : "bg-surface-container border-outline-variant/50 text-on-surface-variant hover:border-outline-variant"
                } ${disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
              >
                {t(`search_docs.mode_${m}`)}
              </button>
            );
          })}
        </div>
        {mode === "answer" && !engineOk && (
          <p className="text-xs text-warning mt-1 flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px]">warning</span>
            {t("search_docs.mode_answer_disabled")}
          </p>
        )}
      </div>

      {watchedFolders.length > 0 && (
        <div>
          <p className="text-sm font-medium text-on-surface mb-2">{t("search_docs.folder_label")}</p>
          <select
            value={sourcePrefix ?? ""}
            onChange={(e) => setSourcePrefix(e.target.value || null)}
            className="w-full px-3 py-2 rounded-xl bg-surface-container border border-outline-variant/50 text-on-surface text-sm focus:outline-none focus:border-primary transition-colors"
          >
            <option value="">{t("search_docs.folder_all")}</option>
            {watchedFolders.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </div>
      )}

      <div className="flex justify-end gap-3 pt-2">
        <button
          onClick={onClose}
          className="px-4 py-2 rounded-full text-sm text-on-surface-variant hover:bg-surface-container"
        >
          {t("search_docs.cancel")}
        </button>
        <button
          onClick={handleSearch}
          disabled={!canSearch}
          className="px-5 py-2 rounded-full bg-primary text-on-primary text-sm disabled:opacity-40"
        >
          {t("search_docs.search_btn")}
        </button>
      </div>
    </div>
  );

  const loadingScreen = (
    <div className="text-center py-8 space-y-3">
      <span className="material-symbols-outlined text-4xl text-primary animate-pulse">search</span>
      <p className="text-on-surface-variant">{t("search_docs.searching")}</p>
    </div>
  );

  const resultsScreen = result ? (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-on-surface">{t("search_docs.results_title")}</h3>

      <p className="text-xs text-on-surface-variant">
        {t("search_docs.results_count", { count: result.hits.length, ms: result.latency_ms })}
      </p>

      {/* Warnings */}
      {result.warnings.length > 0 && (
        <div className="space-y-1">
          {result.warnings.map((w, i) => (
            <p key={i} className="flex items-center gap-1 text-xs text-warning">
              <span className="material-symbols-outlined text-[14px]">warning</span>
              {t(`search_docs.warning_${w}` as any, w)}
            </p>
          ))}
        </div>
      )}

      {/* Answer block */}
      {result.answer && (
        <div className="rounded-xl bg-primary-container/10 border border-primary/20 p-4">
          <p className="text-sm text-on-surface whitespace-pre-wrap">{result.answer}</p>
        </div>
      )}

      {/* Hit list */}
      {result.hits.length === 0 ? (
        <p className="text-sm text-on-surface-variant text-center py-4">{t("search_docs.no_results")}</p>
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto custom-scrollbar">
          {result.hits.map((h) => (
            <div key={h.id} className="rounded-xl bg-surface-container-low/40 border border-outline-variant/10 p-3 space-y-1">
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium text-primary truncate flex-1" title={h.source_path}>
                  <span className="material-symbols-outlined text-[14px] align-text-bottom mr-1">description</span>
                  {h.filename}
                </p>
                <span className="text-[10px] text-on-surface-variant font-mono ml-2">
                  {t("search_docs.chunk_label", { n: h.chunk_index })}
                </span>
              </div>
              <p className="text-sm text-on-surface leading-relaxed">{h.snippet}</p>
              <p className="text-[10px] text-on-surface-variant/60">
                {t("search_docs.score_label")}: {h.score.toFixed(4)}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Disk search link */}
      <button
        onClick={handleDiskSearch}
        className="w-full flex items-center justify-center gap-1.5 text-[11px] text-outline hover:text-on-surface-variant transition-colors"
      >
        <span className="material-symbols-outlined text-[14px]">folder_open</span>
        {t("search_docs.search_disk")}
      </button>

      {/* Action buttons */}
      <div className="flex justify-end gap-3 pt-2 flex-wrap">
        <button
          onClick={handleSaveNote}
          className="px-4 py-2 rounded-full text-sm text-on-surface-variant hover:bg-surface-container"
        >
          {t("search_docs.save_summary")}
        </button>
        {onDocumentsOpen && (
          <button
            onClick={() => { onDocumentsOpen(); onClose(); }}
            className="px-4 py-2 rounded-full text-sm text-on-surface-variant hover:bg-surface-container"
          >
            {t("search_docs.open_documents")}
          </button>
        )}
        {result.hits.length > 0 && (
          <button
            onClick={handleDeepDive}
            className="px-4 py-2 rounded-full bg-primary text-on-primary text-sm"
          >
            {t("search_docs.deep_dive")}
          </button>
        )}
        <button
          onClick={onClose}
          className="px-4 py-2 rounded-full text-sm text-on-surface-variant hover:bg-surface-container"
        >
          {t("search_docs.close")}
        </button>
      </div>
    </div>
  ) : null;

  const errorScreen = (
    <div className="text-center py-6 space-y-3">
      <span className="material-symbols-outlined text-4xl text-error">error</span>
      <p className="text-on-surface font-medium">{t("search_docs.error_title")}</p>
      <p className="text-sm text-on-surface-variant">{errorMsg}</p>
      <div className="flex justify-center gap-3 pt-2">
        <button onClick={onClose} className="px-4 py-2 rounded-full text-sm text-on-surface-variant hover:bg-surface-container">
          {t("search_docs.cancel")}
        </button>
        <button onClick={() => setScreen("search")} className="px-4 py-2 rounded-full bg-primary text-on-primary text-sm">
          {t("search_docs.retry")}
        </button>
      </div>
    </div>
  );

  const screenContent = (
    screen === "search" ? searchScreen :
    screen === "loading" ? loadingScreen :
    screen === "results" ? resultsScreen :
    errorScreen
  );

  return (
    <Dialog open={isOpen} onClose={screen === "loading" ? () => {} : onClose}>
      {screenContent}
    </Dialog>
  );
}
