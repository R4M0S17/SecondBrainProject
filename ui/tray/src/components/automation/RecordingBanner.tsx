import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import type { RecordingStatus } from "../../api/types";
import RecordingPreview from "./RecordingPreview";

interface RecordingBannerProps {
  status: RecordingStatus | null;
  isGeneralizing: boolean;
  onPoll: () => void;
  onStop: () => void;
  onCancel: () => void;
}

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function RecordingBanner({
  status,
  isGeneralizing,
  onPoll,
  onStop,
  onCancel,
}: RecordingBannerProps) {
  const { t } = useTranslation();

  useEffect(() => {
    if (!status?.recording && !isGeneralizing) return;
    const id = window.setInterval(() => {
      onPoll();
    }, 1000);
    return () => window.clearInterval(id);
  }, [status?.recording, isGeneralizing, onPoll]);

  if (!status?.recording && !isGeneralizing) return null;

  return (
    <div className="shrink-0 border-t border-outline-variant/20 bg-surface-container-low/60 px-6 md:px-10 py-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-4 min-w-0">
          <span className="flex items-center gap-2 text-[13px] font-medium text-tertiary-fixed-dim">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 status-dot-pulse" />
            {isGeneralizing ? t("workflows.generating") : t("workflows.recording_banner")}
          </span>
          {!isGeneralizing && status && (
            <>
              <span className="font-mono text-[13px] text-on-surface">
                {formatDuration(status.duration_sec)}
              </span>
              <span className="text-[12px] text-outline">
                {t("workflows.actions_count", { count: status.event_count })}
              </span>
              {status.apps.length > 0 && (
                <span className="text-[12px] text-outline truncate">
                  {status.apps.join(" · ")}
                </span>
              )}
            </>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          {!isGeneralizing && (
            <>
              <button
                type="button"
                onClick={onCancel}
                className="px-4 py-2 text-[12px] rounded-xl bg-surface-container-low text-on-surface-variant hover:bg-surface-container/60 active:scale-[0.98] transition-all"
              >
                {t("workflows.record_cancel")}
              </button>
              <button
                type="button"
                onClick={onStop}
                className="px-4 py-2 text-[12px] rounded-xl bg-primary-container text-on-primary-container font-medium hover:opacity-90 active:scale-[0.98] transition-all"
              >
                {t("workflows.record_stop")}
              </button>
            </>
          )}
        </div>
      </div>
      {!isGeneralizing && status && (
        <div className="mt-3 rounded-xl bg-surface-container-low/40 border border-outline-variant/10">
          <RecordingPreview events={status.preview} />
        </div>
      )}
      {!isGeneralizing && status?.recording && (
        <p className="mt-2 text-[11px] text-outline">{t("workflows.recording_privacy")}</p>
      )}
    </div>
  );
}
