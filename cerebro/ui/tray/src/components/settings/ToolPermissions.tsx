import { useSettingsStore } from "../../stores/settings";
import type { AppConfig } from "../../api/types";

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
              className="h-[44px] flex items-center justify-between px-2 rounded hover:bg-[#1c1b23] transition-colors"
            >
              <span className="text-[14px] text-[#e5e0ed]">{label}</span>
              <button
                onClick={() => toggle(key)}
                role="switch"
                aria-checked={enabled}
                className={`w-8 h-4 rounded-full relative cursor-pointer transition-colors ${
                  enabled ? "bg-[#94a3b8]" : "bg-[#13121b]"
                }`}
              >
                <div
                  className={`absolute top-0.5 w-3 h-3 bg-white rounded-full transition-transform ${
                    enabled ? "right-0.5" : "left-0.5"
                  }`}
                />
              </button>
            </div>
          );
        })}
      </div>
    </section>
  );
}
