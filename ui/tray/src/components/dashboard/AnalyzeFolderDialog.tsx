import { useState, useEffect, useCallback } from "react";
import { open as openFolderPicker } from "@tauri-apps/plugin-dialog";
import { useTranslation } from "react-i18next";
import { useSettingsStore } from "../../stores/settings";
import { useSystemStore } from "../../stores/system";
import { useChatStore } from "../../stores/chat";
import { analyzeFolder } from "../../api/client";
import { buildFolderAnalysisPrompt, type AnalysisMode } from "../../utils/folderAnalysisPrompt";
import Dialog from "../shared/Dialog";
import type { FolderAnalyzeResponse } from "../../api/types";

interface AnalyzeFolderDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

type Screen = "config" | "loading" | "results" | "error";

export default function AnalyzeFolderDialog({ isOpen, onClose }: AnalyzeFolderDialogProps) {
  const { t, i18n } = useTranslation();
  const config = useSettingsStore((s) => s.config);
  const patch = useSettingsStore((s) => s.patch);
  const engineOk = useSystemStore((s) => s.status?.engine_ok ?? false);
  const watchedFolders = config?.watched_folders ?? [];
  const setPendingChatAction = useChatStore((s) => s.setPendingChatAction);

  const [selectedPath, setSelectedPath] = useState("");
  const [mode, setMode] = useState<AnalysisMode>("structure");
  const [screen, setScreen] = useState<Screen>("config");
  const [result, setResult] = useState<FolderAnalyzeResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (isOpen) {
      setSelectedPath("");
      setMode("structure");
      setScreen("config");
      setResult(null);
      setErrorMsg("");
    }
  }, [isOpen]);

  const handleBrowse = useCallback(async () => {
    try {
      const selected = await openFolderPicker({
        directory: true,
        multiple: false,
        title: t("folder.analyze_pick_title"),
      });
      if (selected) setSelectedPath(selected);
    } catch {
      // user cancelled or dialog unavailable (e.g. non-Tauri dev)
    }
  }, [t]);

  const canAnalyze = selectedPath.trim().length > 0;
  const contentModesDisabled = !engineOk && (mode === "content" || mode === "full");

  const handleAnalyze = async () => {
    if (!canAnalyze) return;
    setScreen("loading");

    try {
      const res = await analyzeFolder({ path: selectedPath, max_depth: 4 });
      setResult(res);
      setScreen("results");
    } catch {
      // API unavailable — fall back to Fase 2 chat navigation
      const query = buildFolderAnalysisPrompt(mode, selectedPath, i18n.language, t);
      setPendingChatAction({ query, autoSend: true, agentId: "auto" });
      onClose();
    }
  };

  const handleDeepDive = () => {
    if (!result) return;
    const stats = `Files: ${result.total_files}, Dirs: ${result.total_dirs}, Size: ${result.total_size_mb.toFixed(1)} MB, Indexed: ${result.indexed_count}/${result.total_files}`;
    const query = buildFolderAnalysisPrompt(mode, selectedPath, i18n.language, t) + `\n\nPreliminary stats: ${stats}`;
    setPendingChatAction({ query, autoSend: true, agentId: "auto" });
    onClose();
  };

  const handleSaveReport = async () => {
    if (!result) return;
    const lines = [
      `# Folder analysis: ${result.path}`,
      `Generated: ${new Date().toISOString()}`,
      "",
      "## Summary",
      `- Files: ${result.total_files} | Dirs: ${result.total_dirs} | Size: ${result.total_size_mb.toFixed(1)} MB`,
      `- Indexed: ${result.indexed_count}`,
      "",
      "## Extensions",
      ...Object.entries(result.by_extension)
        .sort(([, a], [, b]) => b - a)
        .map(([ext, count]) => `- ${ext}: ${count}`),
      "",
      "## Largest files",
      ...result.largest_files.map((f) => `- ${f.path} (${(f.size_bytes / 1024).toFixed(1)} KB)`),
      "",
      "## Tree preview",
      "```",
      result.tree_preview,
      "```",
    ];
    if (result.warnings.length > 0) {
      lines.push("", "## Warnings", ...result.warnings.map((w) => `- ${w}`));
    }
    const markdown = lines.join("\n");
    try {
      const { writeQuickNote } = await import("../../api/client");
      await writeQuickNote(markdown, `folder-analysis-${result.path.replace(/[^a-zA-Z0-9]/g, "-")}`);
    } catch {
      // silent
    }
  };

  const configScreen = (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-on-surface">{t("folder.analyze_title")}</h3>

      {/* Step 1 — Select folder */}
      <div>
        <p className="text-sm font-medium text-on-surface mb-2">{t("folder.analyze_select_folder")}</p>
        {watchedFolders.length > 0 && (
          <div className="space-y-1 mb-3">
            {watchedFolders.map((f) => (
              <button
                key={f}
                onClick={() => setSelectedPath(f)}
                className={`w-full text-left px-3 py-2 rounded-lg border text-sm truncate transition-colors ${
                  selectedPath === f
                    ? "bg-primary-container/20 border-primary text-primary"
                    : "bg-surface-container border-outline-variant/50 text-on-surface hover:border-outline-variant"
                }`}
              >
                <span className="material-symbols-outlined text-[16px] align-text-bottom mr-1.5">folder</span>
                {f}
              </button>
            ))}
          </div>
        )}
        {watchedFolders.length === 0 && (
          <p className="text-xs text-on-surface-variant mb-3">{t("folder.analyze_no_watched")}</p>
        )}
        {selectedPath && !watchedFolders.includes(selectedPath) && (
          <div className="mb-3 px-3 py-2 rounded-lg bg-surface-container border border-outline-variant/50 text-sm truncate">
            <span className="material-symbols-outlined text-[16px] align-text-bottom mr-1.5">folder</span>
            {selectedPath}
          </div>
        )}
        <button
          onClick={handleBrowse}
          className="px-4 py-2 rounded-full text-sm bg-surface-container border border-outline-variant/50 text-on-surface hover:bg-surface-container-high transition-colors"
        >
          {t("folder.analyze_browse")}
        </button>
      </div>

      {/* Step 2 — Analysis mode */}
      <div>
        <p className="text-sm font-medium text-on-surface mb-2">{t("folder.analyze_title")}</p>
        <div className="space-y-2">
          {(["structure", "content", "full"] as AnalysisMode[]).map((m) => {
            const disabled = !engineOk && (m === "content" || m === "full");
            return (
              <label
                key={m}
                className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                  mode === m
                    ? "border-primary bg-primary-container/10"
                    : "border-outline-variant/30 bg-surface-container-low/40"
                } ${disabled ? "opacity-40 cursor-not-allowed" : ""}`}
              >
                <input
                  type="radio"
                  name="mode"
                  value={m}
                  checked={mode === m}
                  onChange={() => setMode(m)}
                  disabled={disabled}
                  className="mt-0.5 accent-primary"
                />
                <div>
                  <p className="text-sm font-medium text-on-surface">{t(`folder.analyze_mode_${m}`)}</p>
                  <p className="text-xs text-on-surface-variant">{t(`folder.analyze_mode_${m}_desc`)}</p>
                  {disabled && (
                    <p className="text-xs text-warning mt-1">{t("folder.analyze_engine_required")}</p>
                  )}
                </div>
              </label>
            );
          })}
        </div>
      </div>

      <div className="flex justify-end gap-3 pt-2">
        <button
          onClick={onClose}
          className="px-4 py-2 rounded-full text-sm text-on-surface-variant hover:bg-surface-container"
        >
          {t("folder.analyze_cancel")}
        </button>
        <button
          onClick={handleAnalyze}
          disabled={!canAnalyze || contentModesDisabled}
          className="px-5 py-2 rounded-full bg-primary text-on-primary text-sm disabled:opacity-40"
        >
          {t("folder.analyze_start")}
        </button>
      </div>
    </div>
  );

  const resultsScreen = result ? (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-on-surface truncate" title={result.path}>
        {t("folder.analyze_results_title", { path: result.path })}
      </h3>

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-xl bg-surface-container-low/40 border border-outline-variant/10 p-3 text-center">
          <p className="text-sm text-on-surface-variant">{t("folder.analyze_total_files")}</p>
          <p className="text-xl font-semibold text-on-surface">{result.total_files}</p>
        </div>
        <div className="rounded-xl bg-surface-container-low/40 border border-outline-variant/10 p-3 text-center">
          <p className="text-sm text-on-surface-variant">{t("folder.analyze_total_dirs")}</p>
          <p className="text-xl font-semibold text-on-surface">{result.total_dirs}</p>
        </div>
        <div className="rounded-xl bg-surface-container-low/40 border border-outline-variant/10 p-3 text-center">
          <p className="text-sm text-on-surface-variant">{t("folder.analyze_total_size")}</p>
          <p className="text-xl font-semibold text-on-surface">{result.total_size_mb.toFixed(1)} MB</p>
        </div>
      </div>

      {/* Extensions bar */}
      {Object.keys(result.by_extension).length > 0 && (
        <div>
          <p className="text-xs text-on-surface-variant font-medium mb-1.5 uppercase tracking-wider">Extensions</p>
          <div className="space-y-1">
            {Object.entries(result.by_extension)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 8)
              .map(([ext, count]) => {
                const maxCount = Math.max(...Object.values(result.by_extension));
                const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
                return (
                  <div key={ext} className="flex items-center gap-2 text-xs">
                    <span className="w-12 text-right text-on-surface-variant font-mono">{ext}</span>
                    <div className="flex-1 h-4 rounded bg-surface-container overflow-hidden">
                      <div
                        className="h-full rounded bg-primary-container/30 transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="w-8 text-left text-on-surface font-mono">{count}</span>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Tree preview */}
      {result.tree_preview && (
        <div>
          <p className="text-xs text-on-surface-variant font-medium mb-1.5 uppercase tracking-wider">Tree</p>
          <pre className="font-mono text-[12px] text-on-surface-variant bg-surface-container rounded-lg p-3 max-h-48 overflow-y-auto custom-scrollbar">
            {result.tree_preview}
          </pre>
        </div>
      )}

      {/* Indexed count */}
      <p className="text-xs text-on-surface-variant">
        {t("folder.analyze_indexed_count", { count: result.indexed_count, total: result.total_files })}
      </p>

      {/* Watched folder banner */}
      {!watchedFolders.some((wf) => result.path.startsWith(wf)) && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-400/10 border border-amber-400/20">
          <span className="material-symbols-outlined text-[18px] text-amber-400 shrink-0">visibility_off</span>
          <p className="text-xs text-amber-300 flex-1">{t("folder.analyze_not_watched")}</p>
          <button
            onClick={async () => {
              const merged = Array.from(new Set([...watchedFolders, result.path]));
              await patch({ watched_folders: merged });
            }}
            className="px-3 py-1 rounded-full text-xs bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 transition-colors shrink-0"
          >
            {t("folder.analyze_add_watched")}
          </button>
        </div>
      )}

      {/* Warnings */}
      {result.warnings.length > 0 && (
        <div className="text-xs text-warning space-y-0.5">
          {result.warnings.map((w, i) => (
            <p key={i} className="flex items-center gap-1">
              <span className="material-symbols-outlined text-[14px]">warning</span>
              {w}
            </p>
          ))}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex justify-end gap-3 pt-2">
        <button
          onClick={handleSaveReport}
          className="px-4 py-2 rounded-full text-sm text-on-surface-variant hover:bg-surface-container"
        >
          {t("folder.analyze_save_report")}
        </button>
        <button
          onClick={handleDeepDive}
          className="px-4 py-2 rounded-full bg-primary text-on-primary text-sm"
        >
          {t("folder.analyze_deep_dive")}
        </button>
        <button
          onClick={onClose}
          className="px-4 py-2 rounded-full text-sm text-on-surface-variant hover:bg-surface-container"
        >
          {t("folder.analyze_close")}
        </button>
      </div>
    </div>
  ) : null;

  const loadingScreen = (
    <div className="text-center py-8 space-y-3">
      <span className="material-symbols-outlined text-4xl text-primary animate-pulse">folder_open</span>
      <p className="text-on-surface-variant">{t("folder.analyze_loading")}</p>
    </div>
  );

  const errorScreen = (
    <div className="text-center py-6 space-y-3">
      <span className="material-symbols-outlined text-4xl text-error">error</span>
      <p className="text-on-surface font-medium">{t("folder.analyze_error")}</p>
      <p className="text-sm text-on-surface-variant">{errorMsg}</p>
      <div className="flex justify-center gap-3 pt-2">
        <button onClick={onClose} className="px-4 py-2 rounded-full text-sm text-on-surface-variant hover:bg-surface-container">
          {t("folder.analyze_cancel")}
        </button>
        <button onClick={() => setScreen("config")} className="px-4 py-2 rounded-full bg-primary text-on-primary text-sm">
          {t("folder.analyze_retry")}
        </button>
      </div>
    </div>
  );

  const screenContent = (
    screen === "config" ? configScreen :
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
