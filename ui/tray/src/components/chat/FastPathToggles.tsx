import { useChatStore } from "../../stores/chat";
import { useSettingsStore } from "../../stores/settings";

type FastPathId = "math" | "calendar" | "reminders" | "websearch";

interface FastPathItem {
  id: FastPathId;
  label: string;
  icon: string;
}

const fastPaths: FastPathItem[] = [
  { id: "math", label: "Math", icon: "calculate" },
  { id: "calendar", label: "Calendar", icon: "calendar_today" },
  { id: "reminders", label: "Reminders", icon: "notifications" },
  { id: "websearch", label: "Web Search", icon: "travel_explore" },
];

export default function FastPathToggles() {
  const activeAgent = useChatStore((s) => s.activeAgent);
  const setActiveAgent = useChatStore((s) => s.setActiveAgent);
  const { patch } = useSettingsStore();

  const isActive = (id: FastPathId): boolean => {
    if (id === "calendar") return activeAgent === "calendar";
    if (id === "websearch") return false;
    return false;
  };

  const handleClick = (id: FastPathId) => {
    switch (id) {
      case "calendar":
        setActiveAgent(isActive(id) ? "auto" : "calendar");
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
      case "math":
      case "reminders":
        break;
    }
  };

  return (
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
  );
}
