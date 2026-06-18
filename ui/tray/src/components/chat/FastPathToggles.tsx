import { useState } from "react";
import { useSettingsStore } from "../../stores/settings";
import QuickNoteDialog from "./QuickNoteDialog";

type FastPathId = "quicknote" | "indexnow" | "focusmode" | "websearch";

interface FastPathItem {
  id: FastPathId;
  label: string;
  icon: string;
}

const fastPaths: FastPathItem[] = [
  { id: "quicknote", label: "Quick Note", icon: "note_add" },
  { id: "indexnow", label: "Index Now", icon: "database" },
  { id: "focusmode", label: "Focus Mode", icon: "visibility_off" },
  { id: "websearch", label: "Web Search", icon: "travel_explore" },
];

export default function FastPathToggles() {
  const { patch } = useSettingsStore();
  const [quickNoteOpen, setQuickNoteOpen] = useState(false);

  const config = useSettingsStore((s) => s.config);
  const isActive = (id: FastPathId): boolean => {
    if (id === "websearch") return config?.tool_permissions?.search_web ?? false;
    if (id === "focusmode") return config?.focus_mode ?? false;
    return false;
  };

  const handleClick = (id: FastPathId) => {
    switch (id) {
      case "quicknote":
        setQuickNoteOpen(true);
        break;
      case "indexnow": {
        const folders = config?.watched_folders ?? [];
        if (folders.length > 0) {
          useSettingsStore.getState().startIndexing(folders);
        }
        break;
      }
      case "focusmode":
        void patch({ focus_mode: !isActive(id) });
        break;
      case "websearch": {
        const currentPerms = useSettingsStore.getState().config?.tool_permissions;
        const safePerms = currentPerms ?? {
          execute_python: true,
          write_file: true,
          read_file: true,
          search_web: false,
        };
        void patch({
          tool_permissions: { ...safePerms, search_web: !isActive(id) },
        });
        break;
      }
    }
  };

  return (
    <>
      <div className="flex justify-center gap-3 mb-4">
        {fastPaths.map(({ id, label, icon }) => {
          const active = isActive(id);
          return (
            <button
              key={id}
              onClick={() => handleClick(id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm transition-all group ${
                active
                  ? "border border-primary-container/30 bg-primary-container/10 text-primary-container shadow-[0_0_10px_rgba(37,99,235,0.1)]"
                  : "border border-outline-variant/50 bg-surface-container/30 text-on-surface-variant hover:border-primary-container/50 hover:text-primary-container"
              }`}
            >
              <span className={`material-symbols-outlined text-[18px] ${active ? "" : "group-hover:text-primary-container"}`}>
                {icon}
              </span>
              {label}
            </button>
          );
        })}
      </div>

      <QuickNoteDialog
        open={quickNoteOpen}
        onClose={() => setQuickNoteOpen(false)}
      />
    </>
  );
}
