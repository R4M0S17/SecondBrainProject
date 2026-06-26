import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useSettingsStore } from "../../stores/settings";
import QuickNoteDialog from "./QuickNoteDialog";

type FastPathId = "quicknote" | "indexnow" | "websearch";

const fastPaths: { id: FastPathId; labelKey: string; icon: string }[] = [
  { id: "quicknote", labelKey: "note.quick_note", icon: "note_add" },
  { id: "indexnow", labelKey: "documents.reindex", icon: "database" },
  { id: "websearch", labelKey: "tools.browser", icon: "travel_explore" },
];

export default function FastPathToggles() {
  const { t } = useTranslation();
  const { patch } = useSettingsStore();
  const [quickNoteOpen, setQuickNoteOpen] = useState(false);

  const config = useSettingsStore((s) => s.config);
  const isActive = (id: FastPathId): boolean => {
    if (id === "websearch") return config?.tool_permissions?.search_web ?? false;
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
      <div className="flex justify-center gap-[clamp(0.375rem,1.5vw,0.75rem)] mb-4">
        {fastPaths.map(({ id, labelKey, icon }) => {
          const active = isActive(id);
          const label = t(labelKey);
          return (
            <button
              key={id}
              onClick={() => handleClick(id)}
              className={`flex items-center gap-[clamp(0.25rem,0.8vw,0.5rem)] px-[clamp(0.5rem,2vw,1rem)] py-[clamp(0.25rem,0.9vw,0.5rem)] rounded-full text-[clamp(0.625rem,1.4vw,0.875rem)] transition-all group ${
                active
                  ? "border border-primary-container/30 bg-primary-container/10 text-primary-container shadow-[0_0_10px_rgba(37,99,235,0.1)]"
                  : "border border-outline-variant/50 bg-surface-container/30 text-on-surface-variant hover:border-primary-container/50 hover:text-primary-container"
              }`}
            >
              <span className={`material-symbols-outlined text-[clamp(13px,1.8vw,18px)] ${active ? "" : "group-hover:text-primary-container"}`}>
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
