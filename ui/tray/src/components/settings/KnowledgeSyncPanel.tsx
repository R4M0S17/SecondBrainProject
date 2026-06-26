import { useTranslation } from "react-i18next";
import { useSettingsStore } from "../../stores/settings";
import ToggleSwitch from "../shared/ToggleSwitch";

export default function KnowledgeSyncPanel() {
  const { t } = useTranslation();
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
        <span className="text-[12px] text-on-surface">{t("settings.knowledge_sync")}</span>
        <ToggleSwitch
          enabled={enabled}
          onChange={() => void toggleEnabled()}
          size="md"
          ariaLabel={t("settings.knowledge_sync")}
          className="bg-outline/30"
          knobClassName="shadow-sm"
        />
      </div>
      <p className="text-[10px] text-outline mt-1">
        {enabled
          ? t("knowledge_sync.enabled_text")
          : t("knowledge_sync.disabled_text")}
      </p>
    </div>
  );
}
