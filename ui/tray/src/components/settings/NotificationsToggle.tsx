import { useTranslation } from "react-i18next";
import { useSettingsStore } from "../../stores/settings";
import ToggleSwitch from "../shared/ToggleSwitch";

export default function NotificationsToggle() {
  const { t } = useTranslation();
  const { config, patch } = useSettingsStore();
  const enabled = config?.dnd_enabled ?? false;

  return (
    <div className="flex items-center justify-between px-2 py-3 rounded bg-surface-container">
      <div>
        <p className="text-[14px] text-on-surface">{t("settings.notifications")}</p>
        <p className="text-[11px] text-on-surface-variant/60 mt-0.5">{t("settings.notifications_desc")}</p>
      </div>
      <ToggleSwitch
        enabled={enabled}
        onChange={(v) => void patch({ dnd_enabled: v })}
        size="md"
        ariaLabel={t("settings.notifications")}
        className="bg-background shrink-0"
        knobClassName="shadow"
      />
    </div>
  );
}
