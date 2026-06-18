import { useSettingsStore } from "../../stores/settings";
import ToggleSwitch from "../shared/ToggleSwitch";

export default function KnowledgeSyncPanel() {
  const { config, patch } = useSettingsStore();
  const enabled = config?.knowledge_sync?.enabled ?? false;

  const toggleEnabled = async () => {
    await patch({
      knowledge_sync: {
        ...(config?.knowledge_sync || {}),
        enabled: !enabled,
      },
    });
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <span className="text-[12px] text-on-surface">Enable Knowledge Sync</span>
        <ToggleSwitch
          enabled={enabled}
          onChange={() => void toggleEnabled()}
          size="md"
          ariaLabel="Toggle Knowledge Sync"
          className="bg-outline/30"
          knobClassName="shadow-sm"
        />
      </div>
      <p className="text-[10px] text-outline mt-1">
        {enabled
          ? "Sources are synced automatically. Manage them in the Sources tab (left sidebar)."
          : "Enable to add RSS feeds, GitHub repos, and web pages for automatic knowledge sync."}
      </p>
    </div>
  );
}
