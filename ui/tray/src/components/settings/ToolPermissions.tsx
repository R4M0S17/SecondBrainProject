import { useTranslation } from "react-i18next";
import { useSettingsStore } from "../../stores/settings";
import type { AppConfig } from "../../api/types";
import ToggleSwitch from "../shared/ToggleSwitch";

type PermKey = keyof AppConfig["tool_permissions"];

const PERM_KEYS: PermKey[] = ["execute_python", "write_file", "read_file", "search_web"];

export default function ToolPermissions() {
  const { t } = useTranslation();
  const { config, patch } = useSettingsStore();
  const perms = config?.tool_permissions;

  const toggle = (key: PermKey) => {
    if (!perms) return;
    void patch({
      tool_permissions: { ...perms, [key]: !perms[key] },
    });
  };

  return (
    <section>
      <div className="space-y-1">
        {PERM_KEYS.map((key) => {
          const enabled = perms?.[key] ?? false;
          const label = t("permissions." + key);
          return (
            <div
              key={key}
              className="h-[44px] flex items-center justify-between px-2 rounded hover:bg-surface-container-low transition-colors"
            >
              <span className="text-[14px] text-on-surface">{label}</span>
              <ToggleSwitch
                enabled={enabled}
                onChange={() => toggle(key)}
                size="md"
                ariaLabel={label}
                className="bg-background"
              />
            </div>
          );
        })}
      </div>
    </section>
  );
}
