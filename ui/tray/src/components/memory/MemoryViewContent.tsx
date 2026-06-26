import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMemoryStore } from "../../stores/memory";
import FactsTab from "./FactsTab";
import SessionTab from "./SessionTab";
import RecallTab from "./RecallTab";
import HistoryTab from "./HistoryTab";

type MemoryTab = "facts" | "session" | "recall" | "history";

interface MemoryViewContentProps {
  autoRefresh?: boolean;
  compact?: boolean;
}

export default function MemoryViewContent({ autoRefresh = true, compact = false }: MemoryViewContentProps) {
  const { t } = useTranslation();
  const {
    loading,
    usingMock,
    error,
    errorCode,
    refresh,
    clearError,
  } = useMemoryStore();

  const [activeTab, setActiveTab] = useState<MemoryTab>("facts");

  useEffect(() => {
    if (autoRefresh) void refresh();
  }, [autoRefresh, refresh]);

  const tabs: { key: MemoryTab; label: string; icon: string }[] = [
    { key: "facts", label: t("memory.tab_facts"), icon: "bookmark" },
    { key: "session", label: t("memory.tab_session"), icon: "chat" },
    { key: "recall", label: t("memory.tab_recall"), icon: "psychology" },
    { key: "history", label: t("memory.tab_history"), icon: "history" },
  ];

  return (
    <>
      {error && (
        <div className="flex items-center justify-between gap-2 px-4 py-2 mb-4 bg-error/10 border border-error/20 rounded-lg text-[11px] text-error">
          <span className="truncate">
            {errorCode === "stale_backend"
              ? t("memory.error_stale_backend")
              : errorCode === "unavailable"
                ? t("memory.error_unavailable")
                : errorCode === "offline"
                  ? t("memory.error_offline")
                  : error}
          </span>
          <button type="button" onClick={clearError} className="shrink-0 underline">
            {t("memory.dismiss_error")}
          </button>
        </div>
      )}

      {usingMock && (
        <div className="flex items-center gap-2 px-3 py-2 mb-4 bg-violet-500/5 border border-violet-400/10 rounded-lg text-[10px] text-violet-300/80">
          <span className="material-symbols-outlined text-[14px]">science</span>
          {t("memory.mock_banner")}
        </div>
      )}

      {loading && (
        <p className="text-[12px] text-outline text-center py-8">{t("status.loading")}</p>
      )}

      {!loading && (
        <>
          {/* Tab bar */}
          <div className={`flex gap-1 mb-4 ${compact ? "border-b border-outline-variant/10" : "border-b border-outline-variant/10"}`}>
            {tabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-1.5 px-3 py-2 text-[12px] font-medium transition-colors border-b-2 -mb-px ${
                  activeTab === tab.key
                    ? "border-violet-400 text-violet-300"
                    : "border-transparent text-on-surface-variant/60 hover:text-on-surface-variant hover:border-outline-variant/30"
                }`}
              >
                <span className="material-symbols-outlined text-[16px]">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          {activeTab === "facts" && <FactsTab compact={compact} />}
          {activeTab === "session" && <SessionTab />}
          {activeTab === "recall" && <RecallTab compact={compact} />}
          {activeTab === "history" && <HistoryTab />}
        </>
      )}
    </>
  );
}
