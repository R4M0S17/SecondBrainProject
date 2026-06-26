import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSystemStore } from "../../stores/system";

export default function SwapBanner() {
  const { t } = useTranslation();
  const swapEvent = useSystemStore((s) => s.swapEvent);
  const [showReady, setShowReady] = useState(false);

  useEffect(() => {
    if (swapEvent?.phase === "complete") {
      setShowReady(true);
      const id = setTimeout(() => setShowReady(false), 1500);
      return () => clearTimeout(id);
    } else {
      setShowReady(false);
    }
  }, [swapEvent]);

  if (!swapEvent && !showReady) return null;

  if (showReady && swapEvent?.phase === "complete") {
    return (
      <div className="flex items-center gap-2 px-3 py-2 bg-[#1e1b2e] border-l-2 border-[#22c55e] text-[12px] font-mono text-[#22c55e]">
        <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="currentColor">
          <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" />
        </svg>
        <span>{t("swap.ready", { model: swapEvent.to_model })}</span>
      </div>
    );
  }

  if (!swapEvent) return null;

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-[#1e1b2e] border-l-2 border-[#f59e0b] text-[12px] font-mono text-[#f59e0b]">
      {/* Spinner */}
      <svg
        className="w-3.5 h-3.5 shrink-0 animate-spin"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path d="M21 12a9 9 0 11-6.219-8.56" strokeLinecap="round" />
      </svg>
      <span>
        {t("swap.switching_to", { model: swapEvent.to_model, reason: swapEvent.reason })}
        {"estimated_seconds" in swapEvent && swapEvent.estimated_seconds != null
          ? ` · ~${swapEvent.estimated_seconds}s`
          : ""}
      </span>
    </div>
  );
}
