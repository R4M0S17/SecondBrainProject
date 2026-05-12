import { open } from "@tauri-apps/plugin-dialog";
import { useSettingsStore } from "../../stores/settings";

export default function FolderManager() {
  const { config, patch } = useSettingsStore();
  const folders = config?.watched_folders ?? [];

  const addFolder = async () => {
    try {
      const selected = await open({
        directory: true,
        multiple: true,
        title: "Select folders to watch",
      });
      if (!selected) return;
      const paths = Array.isArray(selected) ? selected : [selected];
      const merged = Array.from(new Set([...folders, ...paths]));
      await patch({ watched_folders: merged });
    } catch {
      // user cancelled
    }
  };

  const removeFolder = async (path: string) => {
    await patch({ watched_folders: folders.filter((f) => f !== path) });
  };

  return (
    <section>
      <div className="space-y-1">
        {folders.map((folder) => (
          <div
            key={folder}
            className="flex items-center justify-between bg-[#242736] p-2 rounded-[6px] group"
          >
            <div className="flex items-center gap-2 overflow-hidden">
              <svg className="w-[18px] h-[18px] text-[#928ea0] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
              </svg>
              <span className="font-mono text-[13px] text-[#e5e0ed] truncate">{folder}</span>
            </div>
            <button
              onClick={() => void removeFolder(folder)}
              className="text-[#c9c4d7] opacity-0 group-hover:opacity-100 transition-opacity ml-2 shrink-0"
              aria-label={`Remove ${folder}`}
            >
              <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        ))}
      </div>
      <button
        onClick={() => void addFolder()}
        className="w-full mt-2 py-2 border border-dashed border-[#242736] rounded-[6px] text-[12px] text-[#8b8fa8] hover:bg-[#35343d] transition-colors flex items-center justify-center gap-1"
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M12 5v14M5 12h14" />
        </svg>
        Add Folder
      </button>
    </section>
  );
}
