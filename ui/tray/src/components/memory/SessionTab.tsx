import { useTranslation } from "react-i18next";
import { useMemoryStore } from "../../stores/memory";

const INTERNAL_KEYS = new Set(["last_web_search_query", "last_web_search_result"]);

export default function SessionTab() {
  const { t, i18n } = useTranslation();
  const { session, addEpisode } = useMemoryStore();

  const lastSearchQuery = session.working_memory["last_web_search_query"] ?? null;

  const autoNotes = Object.entries(session.working_memory).filter(
    ([key]) => !INTERNAL_KEYS.has(key)
  );

  const sessionDuration = session.last_consolidation_at
    ? new Intl.RelativeTimeFormat(i18n.language.startsWith("es") ? "es" : "en", { numeric: "auto" }).format(
        Math.round((session.last_consolidation_at - Date.now()) / (1000 * 60 * 60)),
        "hour"
      )
    : null;

  const handleSaveNoteAsFact = async (key: string, value: string) => {
    try {
      await addEpisode(`${key}: ${value}`, ["auto-note", "session"]);
    } catch {
      /* store error */
    }
  };

  const handleSaveAll = async () => {
    for (const [key, value] of autoNotes) {
      try {
        await addEpisode(`${key}: ${value}`, ["auto-note", "session"]);
      } catch {
        /* skip failed */
      }
    }
  };

  const hasContent = !!(
    lastSearchQuery ||
    session.messages_in_short_term > 0 ||
    autoNotes.length > 0
  );

  if (!hasContent) {
    return (
      <section className="bg-surface-container-low/20 border border-outline-variant/10 rounded-xl p-4 md:p-5">
        <div className="mb-3">
          <h2 className="text-[14px] font-semibold text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] text-outline">chat</span>
            {t("memory.session_title")}
          </h2>
          <p className="text-[11px] text-on-surface-variant/60 mt-1">{t("memory.session_desc")}</p>
        </div>
        <p className="text-[12px] text-outline py-6 text-center">{t("memory.session_empty")}</p>
      </section>
    );
  }

  return (
    <section className="bg-surface-container-low/20 border border-outline-variant/10 rounded-xl p-4 md:p-5">
      <div className="mb-3">
        <h2 className="text-[14px] font-semibold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px] text-outline">chat</span>
          {t("memory.session_title")}
        </h2>
        <p className="text-[11px] text-on-surface-variant/60 mt-1">{t("memory.session_desc")}</p>
      </div>

      <div className="space-y-3">
        {/* Metadata */}
        <div className="flex flex-wrap items-center gap-3 text-[11px] text-on-surface-variant">
          {session.messages_in_short_term > 0 && (
            <span className="flex items-center gap-1">
              <span className="material-symbols-outlined text-[14px] text-outline">chat</span>
              {session.messages_in_short_term} {t("memory.session_messages")}
            </span>
          )}
          {lastSearchQuery && (
            <span className="flex items-center gap-1">
              <span className="material-symbols-outlined text-[14px] text-outline">search</span>
              &ldquo;{lastSearchQuery}&rdquo;
            </span>
          )}
          {sessionDuration && (
            <span className="flex items-center gap-1">
              <span className="material-symbols-outlined text-[14px] text-outline">schedule</span>
              {t("memory.session_duration")} {sessionDuration}
            </span>
          )}
        </div>

        {/* Auto-notes */}
        {autoNotes.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <p className="text-[10px] uppercase tracking-wider text-on-surface-variant/50">
                {t("memory.working_memory")}
              </p>
              <button
                type="button"
                onClick={() => void handleSaveAll()}
                className="text-[11px] text-primary-container hover:underline flex items-center gap-1"
              >
                <span className="material-symbols-outlined text-[14px]">bookmark_add</span>
                {t("memory.save_to_facts")}
              </button>
            </div>
            <dl className="space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
              {autoNotes.map(([key, value]) => (
                <div key={key} className="text-[11px] bg-surface-container/40 rounded-lg p-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <dt className="font-label-mono text-violet-400/80 truncate">{key}</dt>
                      <dd className="text-on-surface-variant mt-0.5 line-clamp-3">{value}</dd>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleSaveNoteAsFact(key, value)}
                      className="shrink-0 px-2 py-1 rounded-md bg-primary-container/15 text-primary-container text-[10px] font-medium hover:bg-primary-container/25 transition-colors flex items-center gap-1"
                      title={t("memory.session_save_note")}
                    >
                      <span className="material-symbols-outlined text-[12px]">bookmark_add</span>
                      <span className="hidden sm:inline">{t("memory.session_save_note")}</span>
                    </button>
                  </div>
                </div>
              ))}
            </dl>
          </div>
        )}
      </div>
    </section>
  );
}
