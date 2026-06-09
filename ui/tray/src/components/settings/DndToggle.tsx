import { useSettingsStore } from "../../stores/settings";

export default function DndToggle() {
  const { config, patch } = useSettingsStore();
  const enabled = config?.dnd_enabled ?? false;

  const toggle = () => {
    void patch({ dnd_enabled: !enabled });
  };

  return (
    <div className="h-[44px] flex items-center justify-between px-2 rounded bg-surface-container">
      <span className="text-[14px] text-on-surface">Do Not Disturb</span>
      <button
        onClick={toggle}
        role="switch"
        aria-checked={enabled}
        aria-label="Toggle Do Not Disturb"
        className={`w-8 h-4 rounded-full relative transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary-container ${
          enabled ? "bg-primary-container" : "bg-background"
        }`}
      >
        <div
          className={`absolute top-0.5 w-3 h-3 bg-white rounded-full shadow transition-transform ${
            enabled ? "translate-x-[18px]" : "translate-x-0.5"
          }`}
        />
      </button>
    </div>
  );
}
