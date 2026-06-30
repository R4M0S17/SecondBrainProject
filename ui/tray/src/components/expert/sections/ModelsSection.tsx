import { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useSettingsStore } from "../../../stores/settings";
import { downloadModel, AVAILABLE_MODELS } from "../../../api/client";
import type { ModelDownloadResponse } from "../../../api/client";

interface DownloadState {
  filename: string;
  status: "downloading" | "done" | "error";
  detail: string;
}

export default function ModelsSection() {
  const { t } = useTranslation();
  const { activeModel, llamaCppModels, llamaCppLoading, switchingModel, patch, loadModels, loadLlamaCppModels } = useSettingsStore();
  const [downloads, setDownloads] = useState<Record<string, DownloadState>>({});

  useEffect(() => {
    loadModels();
    loadLlamaCppModels();
  }, [loadModels, loadLlamaCppModels]);

  const installedNames = new Set(llamaCppModels.map((m) => m.name));
  const activeLower = activeModel?.toLowerCase() ?? "";

  const handleActivate = useCallback((name: string) => {
    void patch({ model: name });
  }, [patch]);

  const handleDownload = useCallback(async (entry: typeof AVAILABLE_MODELS[number]) => {
    setDownloads((prev) => ({
      ...prev,
      [entry.filename]: { filename: entry.filename, status: "downloading", detail: "Downloading..." },
    }));
    try {
      const res: ModelDownloadResponse = await downloadModel(entry.url, entry.filename);
      setDownloads((prev) => ({
        ...prev,
        [entry.filename]: {
          filename: entry.filename,
          status: res.ok ? "done" : "error",
          detail: res.detail,
        },
      }));
      if (res.ok) {
        await loadLlamaCppModels();
      }
    } catch (e) {
      setDownloads((prev) => ({
        ...prev,
        [entry.filename]: {
          filename: entry.filename,
          status: "error",
          detail: e instanceof Error ? e.message : "Download failed",
        },
      }));
    }
  }, [loadLlamaCppModels]);

  return (
    <div className="max-w-2xl space-y-8">
      {/* Installed models */}
      <section>
        <h3 className="text-[13px] font-semibold text-on-surface mb-4">
          {t("expert.models.installed")}
        </h3>
        {llamaCppLoading ? (
          <p className="text-[12px] text-outline">{t("expert.models.loading")}</p>
        ) : llamaCppModels.length === 0 ? (
          <p className="text-[12px] text-outline">{t("expert.models.no_models")}</p>
        ) : (
          <div className="space-y-1">
            {[...llamaCppModels]
              .sort((a, b) => b.size_gb - a.size_gb)
              .map((m) => {
                const isActive = m.name.toLowerCase() === activeLower;
                return (
                  <ModelRow
                    key={m.name}
                    name={m.name}
                    sub={`llama.cpp · ${m.size_gb.toFixed(1)} GB`}
                    badge="GGUF"
                    isActive={isActive}
                    onClick={() => handleActivate(m.name)}
                  />
                );
              })}
          </div>
        )}

        {switchingModel && (
          <div className="flex items-center gap-2 mt-3 px-3 py-2 bg-surface-container border border-outline-variant rounded">
            <span className="inline-block w-3 h-3 border-2 border-outline border-t-transparent rounded-full animate-spin" />
            <span className="text-[11px] text-on-surface-variant">{t("expert.models.switching")}</span>
          </div>
        )}
      </section>

      {/* Available / download models */}
      <section>
        <h3 className="text-[13px] font-semibold text-on-surface mb-4">
          {t("expert.models.available")}
        </h3>
        <div className="space-y-2">
          {AVAILABLE_MODELS.map((entry) => {
            const isInstalled = installedNames.has(entry.filename);
            const dl = downloads[entry.filename];

            return (
              <div
                key={entry.filename}
                className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-surface-container-low border border-outline-variant/30"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-[12px] font-medium text-on-surface truncate">
                    {entry.filename}
                    {isInstalled && (
                      <span className="ml-2 text-[10px] text-success-green font-normal">
                        {t("expert.models.installed_badge")}
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-on-surface-variant mt-0.5">
                    {entry.note} · {entry.sizeGb}
                  </div>
                </div>
                <div className="shrink-0 ml-3">
                  {isInstalled ? (
                    <span className="text-[10px] text-outline font-mono px-2">{entry.sizeGb}</span>
                  ) : dl?.status === "downloading" ? (
                    <span className="flex items-center gap-1.5 text-[11px] text-yellow-500">
                      <span className="inline-block w-2.5 h-2.5 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
                      {t("expert.models.downloading")}
                    </span>
                  ) : dl?.status === "done" ? (
                    <span className="text-[11px] text-success-green">{t("expert.models.downloaded")}</span>
                  ) : dl?.status === "error" ? (
                    <div className="text-right">
                      <span className="text-[11px] text-error block">{t("expert.models.failed")}</span>
                      <span className="text-[9px] text-outline">{dl.detail}</span>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleDownload(entry)}
                      className="px-3 py-1.5 rounded-[6px] bg-primary-container text-on-surface text-[11px] font-semibold hover:bg-primary-container-hover transition-colors"
                    >
                      {entry.sizeGb}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <p className="text-[10px] text-outline mt-2">
          {t("expert.models.install_hint")}
        </p>
      </section>
    </div>
  );
}

function ModelRow({
  name,
  sub,
  badge,
  isActive,
  onClick,
}: {
  name: string;
  sub: string;
  badge?: string;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`flex items-center justify-between p-2.5 rounded-lg cursor-pointer transition-colors ${
        isActive ? "bg-surface-container border-l-2 border-primary-container" : "hover:bg-surface-container-low border-l-2 border-transparent"
      }`}
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <div
          className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0 ${
            isActive ? "border-primary-container" : "border-outline"
          }`}
        >
          {isActive && <div className="w-1.5 h-1.5 bg-primary-container rounded-full" />}
        </div>
        <div className="min-w-0">
          <div className="text-[13px] font-semibold text-on-surface truncate">{name}</div>
          <div className="text-[10px] font-mono text-on-surface-variant">{sub}</div>
        </div>
      </div>
      {badge && (
        <span className="bg-surface-container-higher px-1.5 py-0.5 rounded text-[10px] font-mono text-on-surface-variant shrink-0 ml-2">
          {badge}
        </span>
      )}
    </div>
  );
}
