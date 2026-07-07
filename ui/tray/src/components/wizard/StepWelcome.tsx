import { useTranslation } from "react-i18next";
import { useWizardStore } from "../../stores/wizard";

interface StepWelcomeProps {
  onReady: (ready: boolean) => void;
}

export default function StepWelcome({ onReady }: StepWelcomeProps) {
  const { t } = useTranslation();
  const { setMode, setQuickMode } = useWizardStore();

  const pickQuick = () => {
    setQuickMode(true);
    setMode("local");
    onReady(true);
  };

  const pickAdvanced = () => {
    setQuickMode(false);
    onReady(true);
  };

  return (
    <div className="w-full space-y-4 mb-6">
      <p className="text-[14px] leading-[20px] text-[#e8eaf0] text-center leading-relaxed">
        {t("wizard.welcome_desc")}
      </p>

      <button
        onClick={pickQuick}
        className="w-full p-4 rounded-lg border text-left transition-colors border-outline-variant bg-background hover:border-primary-container hover:bg-[#1a2030]"
      >
        <div className="flex items-center gap-2 mb-1">
          <div className="w-2 h-2 rounded-full bg-success-green" />
          <span className="text-[14px] font-semibold text-on-surface">
            {t("wizard.quick_setup")}
          </span>
          <span className="ml-auto text-[10px] font-bold px-2 py-0.5 rounded bg-success-green/15 text-success-green uppercase tracking-wider">
            {t("wizard.recommended")}
          </span>
        </div>
        <p className="text-[12px] text-outline pl-4">
          {t("wizard.quick_setup_desc")}
        </p>
      </button>

      <button
        onClick={pickAdvanced}
        className="w-full p-4 rounded-lg border text-left transition-colors border-outline-variant bg-background hover:border-outline"
      >
        <div className="flex items-center gap-2 mb-1">
          <div className="w-2 h-2 rounded-full bg-secondary" />
          <span className="text-[14px] font-semibold text-on-surface">
            {t("wizard.advanced_setup")}
          </span>
        </div>
        <p className="text-[12px] text-outline pl-4">
          {t("wizard.advanced_setup_desc")}
        </p>
      </button>
    </div>
  );
}
