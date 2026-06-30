import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useTabStore, type LeftTab } from "../stores/tab";
import { useNotificationStore } from "../stores/notifications";

const tabs: { id: LeftTab; icon: string; labelKey: string }[] = [
  { id: "home", icon: "home", labelKey: "sidebar.home" },
  { id: "chat", icon: "chat", labelKey: "sidebar.chat" },
  { id: "memory", icon: "psychology", labelKey: "sidebar.memory" },
  { id: "workflows", icon: "account_tree", labelKey: "sidebar.workflows" },
  { id: "sources", icon: "rss_feed", labelKey: "sidebar.sources" },
  { id: "code", icon: "terminal", labelKey: "sidebar.code" },
];

export default function LeftSidebar() {
  const { t } = useTranslation();
  const activeTab = useTabStore((s) => s.activeTab);
  const setTab = useTabStore((s) => s.setTab);
  const badges = useNotificationStore((s) => s.badges);
  const clearBadge = useNotificationStore((s) => s.clear);
  const increment = useNotificationStore((s) => s.increment);

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as { tab: LeftTab };
      if (detail?.tab) increment(detail.tab);
    };
    window.addEventListener("cerebro-notification", handler);
    return () => window.removeEventListener("cerebro-notification", handler);
  }, [increment]);

  const handleTabClick = (id: LeftTab) => {
    clearBadge(id);
    setTab(id);
  };

  return (
    <aside className="flex flex-col items-center w-12 bg-surface-container-low/60 backdrop-blur-sm border-r border-outline-variant/20 shrink-0 pt-10 pb-3 gap-1 z-30">
      {tabs.map(({ id, icon, labelKey }, i) => {
        const isActive = activeTab === id;
        const label = t(labelKey);
        const badgeCount = badges[id];
        return (
          <button
            key={id}
            onClick={() => handleTabClick(id)}
            className={`
              sidebar-btn group/item relative flex items-center justify-center h-10 w-10 rounded-xl
              transition-all duration-200 ease-out shrink-0 cursor-pointer
              active:scale-90 active:duration-100
              ${isActive
                ? "bg-primary-container/15 text-primary-container"
                : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container/50"
              }
            `}
            style={{ animationDelay: `${i * 40}ms` }}
            aria-label={label}
          >
            <span
              className={`
                absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-0 rounded-r-full
                transition-all duration-300 ease-out
                ${isActive ? "h-5 bg-primary-container" : "h-0"}
              `}
            />
            <span
              className={`
                material-symbols-outlined text-[20px]
                transition-all duration-200 ease-out
                ${isActive
                  ? "drop-shadow-[0_0_6px_rgba(37,99,235,0.5)]"
                  : "group-hover/item:drop-shadow-[0_0_4px_rgba(228,225,231,0.15)]"
                }
              `}
            >
              {icon}
            </span>
            {badgeCount != null && badgeCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] flex items-center justify-center rounded-full bg-error text-[9px] font-bold text-white leading-none px-[3px]">
                {badgeCount > 9 ? "9+" : badgeCount}
              </span>
            )}
            <div
              className={`
                absolute left-full ml-3 px-2.5 py-1.5 rounded-md
                bg-surface-container-high text-on-surface text-label-caps tracking-wider
                whitespace-nowrap pointer-events-none z-50
                shadow-lg border border-outline-variant/10
                transition-all duration-200 ease-out
                opacity-0 -translate-x-1
                group-hover/item:opacity-100 group-hover/item:translate-x-0
                group-hover/item:delay-[150ms]
              `}
            >
              {label}
            </div>
          </button>
        );
      })}
    </aside>
  );
}
