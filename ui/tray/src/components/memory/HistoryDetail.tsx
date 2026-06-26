import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useHistoryStore } from "../../stores/history";

interface HistoryDetailProps {
  onBack: () => void;
  onDelete: (id: string) => Promise<void>;
}

export default function HistoryDetail({ onBack, onDelete }: HistoryDetailProps) {
  const { t } = useTranslation();
  const { selected } = useHistoryStore();
  const [deleting, setDeleting] = useState(false);

  if (!selected) {
    return (
      <section className="bg-surface-container-low/20 border border-outline-variant/10 rounded-xl p-4 md:p-5">
        <p className="text-[12px] text-outline py-6 text-center">{t("history.select_prompt")}</p>
      </section>
    );
  }

  const dateStr = new Date(selected.started_at).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await onDelete(selected.conv_id);
      onBack();
    } catch {
      setDeleting(false);
    }
  };

  return (
    <section className="bg-surface-container-low/20 border border-outline-variant/10 rounded-xl p-4 md:p-5">
      {/* Back button */}
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-1 text-[11px] text-primary-container hover:underline mb-3"
      >
        <span className="material-symbols-outlined text-[14px]">arrow_back</span>
        {t("history.back")}
      </button>

      {/* Header */}
      <div className="mb-3">
        <h2 className="text-[14px] font-semibold text-on-surface truncate">
          {selected.messages[0]?.content || t("history.untitled")}
        </h2>
        <p className="text-[11px] text-on-surface-variant/60 mt-0.5">
          {dateStr} &middot; {selected.messages.length} {t("history.messages")}
        </p>
      </div>

      {/* Messages */}
      <div className="max-h-72 overflow-y-auto custom-scrollbar space-y-2 mb-4">
        {selected.messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 text-[12px] leading-[17px] ${
                msg.role === "user"
                  ? "bg-primary-container/20 text-on-surface rounded-br-md"
                  : "bg-surface-container/60 text-on-surface-variant rounded-bl-md"
              }`}
            >
              <span
                className={`block text-[9px] uppercase tracking-wider font-semibold mb-0.5 ${
                  msg.role === "user" ? "text-primary-container text-right" : "text-violet-400/70"
                }`}
              >
                {msg.role === "user" ? t("history.you") : "Cerebro"}
              </span>
              <p className="whitespace-pre-wrap break-words">{msg.content}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => void handleDelete()}
          disabled={deleting}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-error/15 text-error text-[11px] font-medium hover:bg-error/25 transition-colors disabled:opacity-40"
        >
          <span className="material-symbols-outlined text-[14px]">delete</span>
          {t("history.delete")}
        </button>
      </div>
    </section>
  );
}
