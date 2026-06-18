import { useSettingsStore } from "../../stores/settings";
import ToggleSwitch from "../shared/ToggleSwitch";

export default function DndToggle() {
  const { config, patch } = useSettingsStore();
  const enabled = config?.dnd_enabled ?? false;

  return (
    <div className="h-[44px] flex items-center justify-between px-2 rounded bg-surface-container">
      <span className="text-[14px] text-on-surface">Do Not Disturb</span>
      <ToggleSwitch
        enabled={enabled}
        onChange={(v) => void patch({ dnd_enabled: v })}
        size="md"
        ariaLabel="Toggle Do Not Disturb"
        className="bg-background"
        knobClassName="shadow"
      />
    </div>
  );
}
