import { open } from "@tauri-apps/plugin-dialog";
import { useSettingsStore } from "../../stores/settings";
import FolderList from "../shared/FolderList";

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
      <FolderList
        folders={folders}
        onAdd={addFolder}
        onRemove={(f) => void removeFolder(f)}
      />
    </section>
  );
}
