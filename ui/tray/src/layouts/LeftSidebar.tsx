import { useTabStore, type LeftTab } from "../stores/tab";

const tabs: { id: LeftTab; icon: string; label: string }[] = [
  { id: "chat", icon: "chat", label: "Chat" },
  { id: "sources", icon: "rss_feed", label: "Sources" },
  { id: "tools", icon: "build", label: "Tools" },
  { id: "code", icon: "code", label: "Code" },
];

export default function LeftSidebar() {
  const activeTab = useTabStore((s) => s.activeTab);
  const setTab = useTabStore((s) => s.setTab);

  return (
    <aside className="flex flex-col items-center w-12 bg-surface-container-low/60 backdrop-blur-sm border-r border-outline-variant/20 shrink-0 py-3 gap-1 z-30">
      {tabs.map(({ id, icon, label }) => (
        <button
          key={id}
          onClick={() => setTab(id)}
          className={`p-2 rounded-lg transition-colors ${
            activeTab === id
              ? "bg-primary-container/15 text-primary-container"
              : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
          }`}
          aria-label={label}
          title={label}
        >
          <span className="material-symbols-outlined text-[20px]">{icon}</span>
        </button>
      ))}
    </aside>
  );
}
