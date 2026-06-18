import { useState, useEffect, useRef } from "react";
import { writeQuickNote } from "../../api/client";
import Dialog from "../shared/Dialog";

interface QuickNoteDialogProps {
  open: boolean;
  onClose: () => void;
}

export default function QuickNoteDialog({ open, onClose }: QuickNoteDialogProps) {
  const [content, setContent] = useState("");
  const [title, setTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);
  const [path, setPath] = useState("");
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setContent("");
      setTitle("");
      setDone(false);
      setPath("");
      setError(null);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  const handleSave = async () => {
    if (!content.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const res = await writeQuickNote(content.trim(), title.trim() || undefined);
      setPath(res.path);
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save note");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose}>
      {done ? (
        <div className="text-center py-6 space-y-3">
          <span className="material-symbols-outlined text-4xl text-primary">check_circle</span>
          <p className="text-on-surface font-medium">Note saved</p>
          <p className="text-sm text-on-surface-variant truncate">{path}</p>
          <button
            onClick={onClose}
            className="mt-2 px-5 py-2 rounded-full bg-primary text-on-primary text-sm"
          >
            Done
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-on-surface">Quick Note</h3>
          <input
            ref={inputRef}
            type="text"
            placeholder="Title (optional)"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-surface-container text-on-surface border border-outline-variant/50 outline-none focus:border-primary text-sm"
          />
          <textarea
            placeholder="Write your note…"
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
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!content.trim() || saving}
              className="px-5 py-2 rounded-full bg-primary text-on-primary text-sm disabled:opacity-40"
            >
              {saving ? "Saving…" : "Save Note"}
            </button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
