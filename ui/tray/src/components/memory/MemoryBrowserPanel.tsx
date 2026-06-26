import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useMemoryStore } from "../../stores/memory";
import MemoryViewContent from "./MemoryViewContent";

interface MemoryBrowserPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

/** Narrow slide-over; prefer the Memory tab for full editing UX. */
export default function MemoryBrowserPanel({ isOpen, onClose }: MemoryBrowserPanelProps) {
  const { t } = useTranslation();
  const refresh = useMemoryStore((s) => s.refresh);

  useEffect(() => {
    if (isOpen) void refresh();
  }, [isOpen, refresh]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex" role="complementary" aria-label={t("memory.browser_title")}>
      <div className="flex-1 bg-black/40" onClick={onClose} aria-hidden="true" />
      <aside className="w-[min(480px,100vw)] h-full bg-surface-container border-l border-outline-variant flex flex-col z-10">
        <header className="h-[48px] flex items-center justify-between px-4 border-b border-outline-variant shrink-0">
          <h2 className="text-[15px] font-semibold text-on-surface">{t("memory.browser_title")}</h2>
          <button type="button" onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-container-highest text-on-surface-variant" aria-label={t("memory.close")}>
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
          <MemoryViewContent autoRefresh={false} compact />
        </div>
      </aside>
    </div>
  );
}
