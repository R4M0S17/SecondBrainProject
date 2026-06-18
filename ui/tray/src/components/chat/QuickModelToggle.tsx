import { useSettingsStore } from "../../stores/settings";
import { useSystemStore } from "../../stores/system";

const MODES = {
  normal: {
    label: "Normal",
    icon: "⚡",
    model: "Qwen3.5-2B-UD-Q4_K_XL.gguf",
    profile: "normal",
  },
  "low-power": {
    label: "Low Power",
    icon: "🔋",
    model: "Qwen2.5-0.5B-Instruct-Q4_K_M.gguf",
    profile: "low-power",
  },
};

export function QuickModelToggle() {
  const { activeModel, switchingModel, patch } = useSettingsStore();
  const currentModel = useSystemStore((s) => s.chatModel);

  // Determinar modo actual basado en el modelo activo
  const isLowPower = currentModel?.includes("0.5B") ?? false;
  const currentMode = isLowPower ? "low-power" : "normal";
  const targetMode = isLowPower ? "normal" : "low-power";

  const handleToggle = async () => {
    const target = MODES[targetMode];
    await patch({
      model: target.model,
      profile: target.profile,
    });
  };

  return (
    <button
      onClick={handleToggle}
      disabled={switchingModel}
      className={`quick-model-toggle ${currentMode}`}
      title={`${switchingModel ? "Switching..." : `Switch to ${MODES[targetMode].label}`}`}
    >
      {switchingModel ? (
        <span className="spinner" />
      ) : (
        <>
          <span className="icon">{MODES[currentMode].icon}</span>
          <span className="label">{MODES[currentMode].label}</span>
        </>
      )}
    </button>
  );
}
