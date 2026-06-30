import { useTranslation } from "react-i18next";
import { useWizardStore } from "../../stores/wizard";

interface StepBackendProps {
  onReady: (ready: boolean) => void;
}

export default function StepBackend({ onReady }: StepBackendProps) {
  const { t } = useTranslation();
  const { mode, setMode } = useWizardStore();

  const pick = (m: "local" | "claude" | "none") => {
    setMode(m);
    onReady(true);
  };

  return (
    <div className="w-full space-y-3 mb-6">
      <p className="text-[14px] leading-[20px] text-[#e8eaf0] text-center">
        {t("wizard.choose_backend")}
      </p>

      <button
        onClick={() => pick("local")}
        className={`w-full p-4 rounded-lg border text-left transition-colors ${
          mode === "local"
            ? "border-primary-container bg-[#1a2030]"
            : "border-outline-variant bg-background hover:border-outline"
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <div className={`w-2 h-2 rounded-full ${mode === "local" ? "bg-success-green" : "bg-outline"}`} />
          <span className="text-[14px] font-semibold text-on-surface">{t("wizard.local_title")}</span>
        </div>
        <p className="text-[12px] text-outline pl-4">
          {t("wizard.local_desc")}
        </p>
      </button>

      <button
        onClick={() => pick("claude")}
        className={`w-full p-4 rounded-lg border text-left transition-colors ${
          mode === "claude"
            ? "border-[#a78bfa] bg-[#1a1030]"
            : "border-outline-variant bg-background hover:border-outline"
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <div className={`w-2 h-2 rounded-full ${mode === "claude" ? "bg-[#a78bfa]" : "bg-outline"}`} />
          <span className="text-[14px] font-semibold text-on-surface">{t("wizard.cloud_title")}</span>
        </div>
        <p className="text-[12px] text-outline pl-4">
          {t("wizard.cloud_desc")}{" "}
          <code className="text-[#a78bfa] bg-[#1a1030] px-1 rounded">ANTHROPIC_API_KEY</code>.
        </p>
      </button>

      <button
        onClick={() => pick("none")}
        className={`w-full p-4 rounded-lg border text-left transition-colors ${
          mode === "none"
            ? "border-outline bg-[#1a1a1a]"
            : "border-outline-variant bg-background hover:border-outline"
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <div className={`w-2 h-2 rounded-full ${mode === "none" ? "bg-outline" : "bg-outline"}`} />
          <span className="text-[14px] font-semibold text-on-surface">{t("wizard.none_title")}</span>
        </div>
        <p className="text-[12px] text-outline pl-4">
          {t("wizard.none_desc")}
        </p>
      </button>
    </div>
  );
}
