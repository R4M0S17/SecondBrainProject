import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSettingsStore, type ExpertSection } from "../../stores/settings";
import ExpertNavItem from "./ExpertNavItem";
import ToolManagerSection from "./sections/ToolManagerSection";
import InferenceSection from "./sections/InferenceSection";
import MemoryRagSection from "./sections/MemoryRagSection";
import ProvidersSection from "./sections/ProvidersSection";
import WebSearchSection from "./sections/WebSearchSection";
import FleetSection from "./sections/FleetSection";
import ObservabilitySection from "./sections/ObservabilitySection";
import ModelsSection from "./sections/ModelsSection";

const NAV_GROUPS: {
  labelKey: string;
  items: { id: ExpertSection; icon: string; labelKey: string }[];
}[] = [
  {
    labelKey: "expert.group.tools",
    items: [
      { id: "tools", icon: "construction", labelKey: "expert.nav.tools" },
    ],
  },
  {
    labelKey: "expert.group.engine",
    items: [
      { id: "models", icon: "memory", labelKey: "expert.nav.models" },
      { id: "inference", icon: "psychiatry", labelKey: "expert.nav.inference" },
      { id: "memory-rag", icon: "memory", labelKey: "expert.nav.memory_rag" },
      { id: "providers", icon: "key", labelKey: "expert.nav.providers" },
      { id: "paths", icon: "folder", labelKey: "expert.nav.paths" },
    ],
  },
  {
    labelKey: "expert.group.network",
    items: [
      { id: "web-search", icon: "travel_explore", labelKey: "expert.nav.web_search" },
      { id: "fleet", icon: "dns", labelKey: "expert.nav.fleet" },
    ],
  },
  {
    labelKey: "expert.group.system",
    items: [
      { id: "observability", icon: "monitoring", labelKey: "expert.nav.observability" },
    ],
  },
];

export default function ExpertSettingsModal() {
  const { t } = useTranslation();
  const { expertOpen, activeExpertSection, closeExpert, setExpertSection, expertSaving } = useSettingsStore();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (expertOpen) {
      requestAnimationFrame(() => setVisible(true));
    } else {
      setVisible(false);
    }
  }, [expertOpen]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeExpert();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [closeExpert]);

  if (!expertOpen) return null;

  const renderSection = () => {
    switch (activeExpertSection) {
      case "tools":
        return <ToolManagerSection />;
      case "models":
        return <ModelsSection />;
      case "inference":
        return <InferenceSection />;
      case "memory-rag":
        return <MemoryRagSection />;
      case "providers":
        return <ProvidersSection />;
      case "web-search":
        return <WebSearchSection />;
      case "fleet":
        return <FleetSection />;
      case "observability":
        return <ObservabilitySection />;
      default:
        return (
          <div className="flex items-center justify-center h-full text-on-surface-variant text-[14px]">
            {t("expert.section_coming_soon")}
          </div>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-8">
      <div
        className={`absolute inset-0 bg-black/50 transition-opacity duration-150 ${
          visible ? "opacity-100" : "opacity-0"
        }`}
        onClick={closeExpert}
      />
      <div
        className={`relative w-[85vw] max-w-[1100px] h-[88vh] bg-surface-container rounded-2xl border border-outline-variant shadow-2xl flex overflow-hidden transition-all duration-[180ms] ease-out ${
          visible ? "opacity-100 scale-100" : "opacity-0 scale-[0.97]"
        }`}
      >
        {/* Left nav */}
        <nav className="w-[200px] shrink-0 bg-surface-container-low border-r border-outline-variant p-3 flex flex-col gap-1 overflow-y-auto custom-scrollbar">
          {NAV_GROUPS.map((group) => (
            <div key={group.labelKey}>
              <div className="text-[9px] font-bold tracking-[0.1em] text-outline uppercase px-3 py-1.5">
                {t(group.labelKey)}
              </div>
              {group.items.map((item) => (
                <ExpertNavItem
                  key={item.id}
                  id={item.id}
                  icon={item.icon}
                  label={t(item.labelKey)}
                  active={activeExpertSection === item.id}
                  onClick={() => setExpertSection(item.id)}
                />
              ))}
            </div>
          ))}
        </nav>

        {/* Right content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Header */}
          <header className="h-[48px] flex items-center justify-between px-6 border-b border-outline-variant shrink-0">
            <div className="flex items-center gap-3">
              <h2 className="text-[15px] font-semibold text-on-surface">
                {t("expert.title")}
              </h2>
              {expertSaving && (
                <span className="flex items-center gap-1.5 text-[11px] text-yellow-500">
                  <span className="inline-block w-2 h-2 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
                  {t("expert.saving")}
                </span>
              )}
            </div>
            <button
              onClick={closeExpert}
              className="p-1.5 rounded hover:bg-surface-container-highest transition-colors text-on-surface-variant"
              aria-label="Close expert settings"
            >
              <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </header>

          {/* Scrollable content */}
          <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
            {renderSection()}
          </div>
        </div>
      </div>
    </div>
  );
}
