import { useState } from "react";
import { useTranslation } from "react-i18next";
import TerminalTab from "./TerminalTab";
import OutputTab from "./OutputTab";
import ScratchTab from "./ScratchTab";

type CodeTab = "terminal" | "output" | "scratch";

const TAB_IDS: { id: CodeTab; icon: string }[] = [
  { id: "terminal", icon: "terminal" },
  { id: "output", icon: "output" },
  { id: "scratch", icon: "edit_note" },
];

export default function CodePanel() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<CodeTab>("terminal");

  return (
    <div className="flex-1 flex flex-col overflow-hidden px-4 md:px-6 lg:px-8 pt-4 pb-6 w-full min-w-0">
      <div className="flex items-center justify-between border-b border-outline-variant/20 mb-5 pb-3">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-[22px] text-primary-container">code</span>
          <h2 className="text-[15px] font-semibold text-on-surface">{t("code.title")}</h2>
        </div>
        <div className="flex gap-1">
          {TAB_IDS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-[12px] font-medium rounded-md transition-all ${
                activeTab === tab.id
                  ? "bg-primary-container/10 text-primary-container shadow-sm"
                  : "text-on-surface-variant/60 hover:text-on-surface hover:bg-surface-container-low"
              }`}
            >
              <span className="material-symbols-outlined text-[16px]">{tab.icon}</span>
                {t("code." + tab.id)}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 flex flex-col min-h-0" style={{ display: activeTab === "terminal" ? "flex" : "none" }}>
        <TerminalTab />
      </div>

      <div className="flex-1 flex flex-col min-h-0" style={{ display: activeTab === "output" ? "flex" : "none" }}>
        <OutputTab />
      </div>

      <div className="flex-1 flex flex-col min-h-0" style={{ display: activeTab === "scratch" ? "flex" : "none" }}>
        <ScratchTab />
      </div>
    </div>
  );
}
