import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";

interface StepFoldersProps {
  onReady: (ready: boolean, folders: string[]) => void;
}

export default function StepFolders({ onReady }: StepFoldersProps) {
  const [folders, setFolders] = useState<string[]>([]);

  const addFolders = async () => {
    try {
      const selected = await open({
        directory: true,
        multiple: true,
        title: "Select folders to watch",
      });
      if (!selected) return;
      const paths = Array.isArray(selected) ? selected : [selected];
      const merged = Array.from(new Set([...folders, ...paths]));
      setFolders(merged);
      onReady(merged.length > 0, merged);
    } catch {
      // user cancelled dialog
    }
  };

  const removeFolder = (path: string) => {
    const next = folders.filter((f) => f !== path);
    setFolders(next);
    onReady(next.length > 0, next);
  };

  return (
    <div className="w-full space-y-3 mb-6">
      <p className="text-[14px] text-[#e8eaf0] text-center leading-relaxed">
        Choose the folders Cerebro will index and keep in memory. You can change
        these later in Settings.
      </p>

      {/* Folder list */}
      {folders.length > 0 && (
        <div className="space-y-1">
          {folders.map((f) => (
            <div
              key={f}
              className="flex items-center justify-between bg-[#242736] px-3 py-2 rounded-[6px] group"
            >
              <div className="flex items-center gap-2 overflow-hidden">
                <svg className="w-4 h-4 text-[#928ea0] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                </svg>
                <span className="font-mono text-[13px] text-[#e5e0ed] truncate">{f}</span>
              </div>
              <button
                onClick={() => removeFolder(f)}
                className="text-[#8b8fa8] hover:text-[#ffb4ab] ml-2 shrink-0 transition-colors"
                aria-label={`Remove ${f}`}
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add folder button */}
      <button
        onClick={addFolders}
        className="w-full py-2 border border-dashed border-[#242736] rounded-[6px] text-[12px] text-[#8b8fa8] hover:bg-[#201f27] transition-colors flex items-center justify-center gap-1"
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M12 5v14M5 12h14" />
        </svg>
        Add Folder
      </button>

      {folders.length === 0 && (
        <p className="text-[11px] text-[#8b8fa8] text-center">
          At least one folder is required to continue.
        </p>
      )}
    </div>
  );
}
