import { useTranslation } from "react-i18next";
import MemoryViewContent from "./MemoryViewContent";

export default function MemoryView() {
  const { t } = useTranslation();

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 md:px-10 pt-6 pb-3 shrink-0">
        <h1 className="text-display-lg text-on-surface">{t("memory.tab_title")}</h1>
        <p className="text-body-base text-on-surface-variant/70 mt-1">{t("memory.tab_subtitle")}</p>
      </div>
      <div className="flex-1 overflow-y-auto px-6 md:px-10 pb-8 custom-scrollbar">
        <MemoryViewContent autoRefresh />
      </div>
    </div>
  );
}
