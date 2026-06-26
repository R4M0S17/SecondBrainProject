import { useTranslation } from "react-i18next";
import { useSettingsStore } from "../../stores/settings";
import ToggleSwitch from "../shared/ToggleSwitch";

export default function FocusModeToggle() {
  const { t } = useTranslation();
  const { config, patch } = useSettingsStore();
  const enabled = config?.focus_mode ?? false;

  return (
    <div className="flex items-center justify-between px-2 py-3 rounded bg-surface-container">
      <div>
        <p className="text-[14px] text-on-surface">{t("settings.focus_mode")}</p>
        <p className="text-[11px] text-on-surface-variant/60 mt-0.5">{t("settings.focus_mode_desc")}</p>
      </div>
      <ToggleSwitch
        enabled={enabled}
        onChange={(v) => void patch({ focus_mode: v })}
        size="md"
        ariaLabel={t("settings.focus_mode")}
        className="bg-background shrink-0"
        knobClassName="shadow"
      />
    </div>
  );
}
