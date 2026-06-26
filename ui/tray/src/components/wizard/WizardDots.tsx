import React from "react";
import { useTranslation } from "react-i18next";

interface WizardDotsProps {
  step: number;
  total: number;
  label: string;
}

export default function WizardDots({ step, total, label }: WizardDotsProps) {
  const { t } = useTranslation();
  return (
    <div className="w-full flex flex-col items-center mb-6">
      <div className="flex items-center gap-1 mb-2">
        {Array.from({ length: total }).map((_, idx) => (
          <React.Fragment key={idx}>
            <div
              className={`w-2 h-2 rounded-full transition-colors ${
                idx <= step ? "bg-primary-container" : "border border-outline"
              }`}
            />
            {idx < total - 1 && (
              <div className="w-8 h-[1px] bg-surface-container" />
            )}
          </React.Fragment>
        ))}
      </div>
      <p className="text-[11px] font-bold tracking-[0.05em] uppercase leading-[16px]">
        <span className="text-outline">{t("wizard.step_label", { step: step + 1, total })} · </span>
        <span className="text-[#e8eaf0]">{label}</span>
      </p>
    </div>
  );
}
