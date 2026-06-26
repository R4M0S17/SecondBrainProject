import { useTranslation } from "react-i18next";
import { useSettingsStore } from "../../stores/settings";

/** Low Power (0.5B Nano) — disabled until Nano v2 ships. See docs/plans/LOW_POWER_V2_NANO_MODE.md */
export default function ModelModeToggle() {
  const { t } = useTranslation();
  const { config } = useSettingsStore();
  const available = config?.low_power_available === true;

  return (
    <div className="relative opacity-90">
      <div className="flex items-center justify-between px-4 py-3 rounded-lg bg-surface-container border border-outline-variant border-dashed">
        <div className="flex items-center gap-3 min-w-0">
          <span className="material-symbols-outlined text-[18px] text-outline shrink-0">bolt</span>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-[13px] font-semibold text-on-surface leading-tight">
                {t("settings.lowPower.title")}
              </p>
              <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-surface-container-highest text-outline">
                {t("settings.lowPower.badge")}
              </span>
            </div>
            <p className="text-[10px] text-outline mt-[2px] leading-snug">
              {t("settings.lowPower.description")}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-2">
          <span className="text-[10px] font-medium text-outline select-none hidden sm:inline">
            {t("settings.lowPower.normalActive")}
          </span>
          <div
            className="w-10 h-5 rounded-full bg-outline/20 relative cursor-not-allowed"
            aria-hidden
            title={t("settings.lowPower.disabledHint")}
          >
            <div className="absolute left-0.5 top-0.5 w-4 h-4 rounded-full bg-outline/40 shadow-sm" />
          </div>
        </div>
      </div>
      {!available && (
        <p className="text-[10px] text-outline mt-1.5 px-1 leading-relaxed">
          {t("settings.lowPower.planHint")}
        </p>
      )}
    </div>
  );
}
