import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { MemoryEpisode } from "../../api/types";

interface MemoryEpisodeCardProps {
  episode: MemoryEpisode;
  expanded?: boolean;
  onToggleExpand?: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onTogglePin: () => void;
  highlighted?: boolean;
}

function formatEpisodeDate(ts: number, locale: string): string {
  const rtf = new Intl.RelativeTimeFormat(locale.startsWith("es") ? "es" : "en", { numeric: "auto" });
  const diffMs = ts - Date.now();
  const mins = Math.round(diffMs / 60000);
  if (Math.abs(mins) < 60) return rtf.format(mins, "minute");
  const hours = Math.round(mins / 60);
  if (Math.abs(hours) < 24) return rtf.format(hours, "hour");
  const days = Math.round(hours / 24);
  return rtf.format(days, "day");
}

const SOURCE_META: Record<MemoryEpisode["source"], { label: string; icon: string }> = {
  episode: { label: "memory.source_episode", icon: "smart_toy" },
  consolidation: { label: "memory.source_consolidation", icon: "description" },
  archived: { label: "memory.source_archived", icon: "archive" },
  manual: { label: "memory.source_manual", icon: "bookmark" },
};

export default function MemoryEpisodeCard({
  episode,
  expanded = false,
  onToggleExpand,
  onEdit,
  onDelete,
  onTogglePin,
  highlighted = false,
}: MemoryEpisodeCardProps) {
  const { t, i18n } = useTranslation();
  const [copied, setCopied] = useState(false);
  const sourceMeta = SOURCE_META[episode.source];
  const preview = episode.content.length > 140 && !expanded
    ? `${episode.content.slice(0, 140)}…`
    : episode.content;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(episode.content);
    } catch {
      /* clipboard API not available (Tauri may need @tauri-apps/plugin-clipboard-manager) */
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <article
      className={`bg-surface-container-low/60 border rounded-xl p-3 transition-all ${
        episode.pinned ? "border-violet-400/30" : "border-outline-variant/10"
      } ${
        highlighted ? "ring-2 ring-violet-400/50 ring-offset-1 ring-offset-surface-container" : ""
      }`}
      onKeyDown={(e) => {
        if (e.key === "Escape" && expanded && onToggleExpand) {
          onToggleExpand();
        }
      }}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex flex-wrap items-center gap-1.5 min-w-0">
          {episode.pinned && (
            <span className="material-symbols-outlined text-[14px] text-violet-400" title={t("memory.pinned")}>
              push_pin
            </span>
          )}
          <span className="material-symbols-outlined text-[14px] text-on-surface-variant/50" title={t(sourceMeta.label)}>
            {sourceMeta.icon}
          </span>
          <span className="text-[10px] uppercase tracking-wider font-semibold text-on-surface-variant/60">
            {t(sourceMeta.label)}
          </span>
          <span className="text-[10px] text-outline font-label-mono">
            {formatEpisodeDate(episode.created_at, i18n.language)}
          </span>
        </div>
        <div className="flex items-center gap-0.5 shrink-0">
          <button
            type="button"
            onClick={onEdit}
            className="p-1 rounded hover:bg-surface-container-highest text-on-surface-variant transition-colors"
            aria-label={t("memory.edit_episode")}
          >
            <span className="material-symbols-outlined text-[16px]">edit</span>
          </button>
          <button
            type="button"
            onClick={onTogglePin}
            className="p-1 rounded hover:bg-surface-container-highest text-on-surface-variant transition-colors"
            aria-label={episode.pinned ? t("memory.unpin") : t("memory.pin")}
          >
            <span className="material-symbols-outlined text-[16px]">
              {episode.pinned ? "keep" : "keep_off"}
            </span>
          </button>
          <button
            type="button"
            onClick={() => void handleCopy()}
            className="p-1 rounded hover:bg-surface-container-highest text-on-surface-variant transition-colors"
            aria-label={t("memory.copy_episode")}
            title={copied ? t("memory.copied") : t("memory.copy_episode")}
          >
            <span className="material-symbols-outlined text-[16px]">
              {copied ? "check" : "content_copy"}
            </span>
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="p-1 rounded hover:bg-surface-container-highest text-on-surface-variant hover:text-error transition-colors"
            aria-label={t("memory.delete_episode")}
          >
            <span className="material-symbols-outlined text-[16px]">delete</span>
          </button>
        </div>
      </div>

      <p className="text-[12px] text-on-surface leading-[18px] whitespace-pre-wrap break-words">
        {preview}
      </p>

      {episode.content.length > 140 && onToggleExpand && (
        <button
          type="button"
          onClick={onToggleExpand}
          className="text-[11px] text-primary-container mt-1.5 hover:underline"
        >
          {expanded ? t("memory.show_less") : t("memory.show_more")}
        </button>
      )}

      <div className="flex flex-wrap items-center gap-1.5 mt-2.5">
        {episode.tags.map((tag) => (
          <span
            key={tag}
            className="text-[10px] px-1.5 py-0.5 rounded-md bg-surface-container text-on-surface-variant font-label-mono"
          >
            {tag}
          </span>
        ))}
        <span className="text-[10px] text-outline ml-auto font-label-mono">
          {Math.round(episode.confidence * 100)}%
        </span>
      </div>
    </article>
  );
}
