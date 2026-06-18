import { useSettingsStore } from "../../stores/settings";
import type { AppConfig } from "../../api/types";
import ToggleSwitch from "../shared/ToggleSwitch";

type PermKey = keyof AppConfig["tool_permissions"];

interface PermRow {
  key: PermKey;
  label: string;
}

const PERMISSIONS: PermRow[] = [
  { key: "execute_python", label: "Execute Python" },
  { key: "write_file", label: "Write File" },
  { key: "read_file", label: "Read File" },
  { key: "search_web", label: "Search Web" },
];

export default function ToolPermissions() {
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
        {PERMISSIONS.map(({ key, label }) => {
          const enabled = perms?.[key] ?? false;
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
                ariaLabel={`Toggle ${label}`}
                className="bg-background"
              />
            </div>
          );
        })}
      </div>
    </section>
  );
}
