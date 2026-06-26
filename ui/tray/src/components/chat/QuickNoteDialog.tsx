import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useChatStore } from "../../stores/chat";
import { useDashboardStore } from "../../stores/dashboard";
import { useSettingsStore } from "../../stores/settings";
import { writeQuickNote, createMemoryEpisode } from "../../api/client";
import Dialog from "../shared/Dialog";

interface QuickNoteDialogProps {
  open: boolean;
  onClose: () => void;
  showPostSaveActions?: boolean;
}

type NoteDestination = "file" | "memory";

export default function QuickNoteDialog({ open, onClose, showPostSaveActions }: QuickNoteDialogProps) {
  const { t } = useTranslation();
  const [content, setContent] = useState("");
  const [title, setTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);
  const [path, setPath] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [destination, setDestination] = useState<NoteDestination>("file");
  const [indexing, setIndexing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setContent("");
      setTitle("");
      setDone(false);
      setPath("");
      setError(null);
      setDestination("file");
      setIndexing(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  const handleSave = async () => {
    if (!content.trim()) return;
    setSaving(true);
    setError(null);
    try {
      if (destination === "memory") {
        const tags = title.trim() ? ["quick-note", title.trim()] : ["quick-note"];
        await createMemoryEpisode(content.trim(), tags);
        setPath(t("note.saved"));
        setDone(true);
      } else {
        const res = await writeQuickNote(content.trim(), title.trim() || undefined);
        setPath(res.path);
        setDone(true);
      }
      useDashboardStore.getState().pushActivity({
        id: "",
        label: t("note.quick_note"),
        description: path || content.slice(0, 60),
        timestamp: new Date(),
        icon: "edit_note",
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : t("note.failed"));
    } finally {
      setSaving(false);
    }
  };

  const handleOpenInChat = () => {
    const query = title.trim()
      ? `Resume and expand this note: ${path}\n\nTitle: ${title}\nContent: ${content}`
      : `Resume and expand this note: ${path}\n\n${content}`;
    useChatStore.getState().setPendingChatAction({ query, autoSend: false, agentId: "auto" });
    onClose();
  };

  const handleIndexNow = async () => {
    if (!path) return;
    setIndexing(true);
    try {
      const dir = path.substring(0, path.lastIndexOf("/"));
      await useSettingsStore.getState().startIndexing([dir]);
    } catch {
      // silent
    } finally {
      setIndexing(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose}>
      {done ? (
        <div className="text-center py-6 space-y-3">
          <span className="material-symbols-outlined text-4xl text-primary">check_circle</span>
          <p className="text-on-surface font-medium">{t("note.saved")}</p>
          <p className="text-sm text-on-surface-variant truncate">{path}</p>
          <div className="flex justify-center gap-3 mt-2 flex-wrap">
            <button onClick={onClose} className="px-5 py-2 rounded-full bg-primary text-on-primary text-sm">
              {t("note.done")}
            </button>
            {showPostSaveActions && (
              <>
                <button
                  onClick={handleOpenInChat}
                  className="px-4 py-2 rounded-full text-sm text-on-surface-variant hover:bg-surface-container border border-outline-variant/30"
                >
                  {t("note.open_in_chat")}
                </button>
                <button
                  onClick={handleIndexNow}
                  disabled={indexing || !path}
                  className="px-4 py-2 rounded-full text-sm text-on-surface-variant hover:bg-surface-container border border-outline-variant/30 disabled:opacity-40"
                >
                  {indexing ? t("note.indexing") : t("note.index_now")}
                </button>
              </>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-on-surface">{t("note.quick_note")}</h3>

          {/* Destination selector */}
          {showPostSaveActions && (
            <div className="flex gap-2">
              {(["file", "memory"] as NoteDestination[]).map((d) => (
                <button
                  key={d}
                  onClick={() => setDestination(d)}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm border transition-colors ${
                    destination === d
                      ? "bg-primary-container/20 border-primary text-primary"
                      : "bg-surface-container border-outline-variant/50 text-on-surface-variant hover:border-outline-variant"
                  }`}
                >
                  <span className="material-symbols-outlined text-[16px] align-text-bottom mr-1">
                    {d === "file" ? "description" : "psychology"}
                  </span>
                  {t(`note.dest_${d}`)}
                </button>
              ))}
            </div>
          )}

          <input
            ref={inputRef}
            type="text"
            placeholder={t("note.title_placeholder")}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-surface-container text-on-surface border border-outline-variant/50 outline-none focus:border-primary text-sm"
          />
          <textarea
            placeholder={t("note.content_placeholder")}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={5}
            className="w-full px-3 py-2 rounded-lg bg-surface-container text-on-surface border border-outline-variant/50 outline-none focus:border-primary resize-none text-sm"
          />
          {error && (
            <div className="text-[12px] text-error flex items-center gap-1.5">
              <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4M12 16h.01" />
              </svg>
              {error}
            </div>
          )}
          <div className="flex justify-end gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-full text-sm text-on-surface-variant hover:bg-surface-container"
            >
              {t("note.cancel")}
            </button>
            <button
              onClick={handleSave}
              disabled={!content.trim() || saving}
              className="px-5 py-2 rounded-full bg-primary text-on-primary text-sm disabled:opacity-40"
            >
              {saving ? t("note.saving") : t("note.save")}
            </button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
