import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { MemoryEpisode } from "../../api/types";

interface MemoryEpisodeEditorProps {
  episode: MemoryEpisode;
  onSave: (content: string, tags: string[]) => Promise<void>;
  onClose: () => void;
}

export default function MemoryEpisodeEditor({ episode, onSave, onClose }: MemoryEpisodeEditorProps) {
  const { t } = useTranslation();
  const [content, setContent] = useState(episode.content);
  const [tagsText, setTagsText] = useState(episode.tags.join(", "));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    const trimmed = content.trim();
    if (!trimmed) {
      setError(t("memory.edit_empty"));
      return;
    }
    const tags = tagsText
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    if (episode.pinned) tags.push("pinned");
    setSaving(true);
    setError(null);
    try {
      await onSave(trimmed, tags.length ? tags : ["manual"]);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("memory.edit_failed"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/50" role="dialog" aria-modal="true">
      <div className="w-full max-w-lg bg-surface-container border border-outline-variant rounded-xl shadow-xl flex flex-col max-h-[85vh]">
        <header className="flex items-center justify-between px-4 py-3 border-b border-outline-variant/20 shrink-0">
          <h3 className="text-[14px] font-semibold text-on-surface">{t("memory.edit_episode")}</h3>
          <button type="button" onClick={onClose} className="p-1 rounded hover:bg-surface-container-highest text-on-surface-variant">
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </header>
        <div className="p-4 space-y-3 overflow-y-auto custom-scrollbar">
          {episode.source !== "manual" && (
            <p className="text-[11px] text-amber-400/90 bg-amber-400/5 border border-amber-400/20 rounded-lg px-3 py-2">
              {t("memory.edit_auto_hint")}
            </p>
          )}
          <div>
            <label className="text-[11px] font-medium text-on-surface-variant uppercase tracking-wider">
              {t("memory.edit_content_label")}
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={6}
              className="mt-1.5 w-full bg-surface-container-low border border-outline-variant/20 rounded-lg px-3 py-2 text-[13px] text-on-surface resize-y min-h-[120px] focus:outline-none focus:border-primary-container/50"
            />
          </div>
          <div>
            <label className="text-[11px] font-medium text-on-surface-variant uppercase tracking-wider">
              {t("memory.edit_tags_label")}
            </label>
            <input
              type="text"
              value={tagsText}
              onChange={(e) => setTagsText(e.target.value)}
              placeholder={t("memory.edit_tags_placeholder")}
              className="mt-1.5 w-full bg-surface-container-low border border-outline-variant/20 rounded-lg px-3 py-2 text-[12px] text-on-surface focus:outline-none focus:border-primary-container/50"
            />
          </div>
          {error && <p className="text-[11px] text-error">{error}</p>}
        </div>
        <footer className="flex justify-end gap-2 px-4 py-3 border-t border-outline-variant/20 shrink-0">
          <button type="button" onClick={onClose} className="px-3 py-1.5 text-[12px] text-on-surface-variant">
            {t("note.cancel")}
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            className="px-4 py-1.5 rounded-lg bg-primary-container text-on-primary text-[12px] font-medium disabled:opacity-50"
          >
            {saving ? t("status.loading") : t("memory.save_episode")}
          </button>
        </footer>
      </div>
    </div>
  );
}
