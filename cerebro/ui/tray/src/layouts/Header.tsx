import AgentSelectorDropdown from "../components/shared/AgentSelectorDropdown";
import { useSettingsStore } from "../stores/settings";
import { useSystemStore, selectIsClaudeMode } from "../stores/system";

export default function Header() {
  const { open } = useSettingsStore();
  const isCloud = selectIsClaudeMode(useSystemStore((s) => s.status));

  return (
    <header
      data-tauri-drag-region
      className="flex justify-between items-center w-full px-3 bg-[#1c1b23] border-b border-[#242736] h-[48px] shrink-0"
      role="banner"
    >
      <div className="flex items-center gap-2">
        <img src="/whitelogo.svg" alt="Cerebro" className="h-7 w-7 object-contain shrink-0" />
        {isCloud && (
          <span className="text-[9px] font-bold tracking-widest uppercase px-1.5 py-0.5 rounded bg-[#2d1f4a] text-[#a78bfa] font-mono">
            API
          </span>
        )}
        <AgentSelectorDropdown />
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={open}
          className="p-1 rounded text-[#c9c4d7] hover:bg-[#35343d] transition-colors"
          aria-label="Open settings"
          title="Settings (⌘,)"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 00.12-.61l-1.92-3.32a.49.49 0 00-.59-.22l-2.39.96a7 7 0 00-1.62-.94l-.36-2.54A.484.484 0 0014 2h-4c-.25 0-.46.18-.49.42l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.49.49 0 00-.59.22L2.74 8.87a.49.49 0 00.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58a.49.49 0 00-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.37 1.04.7 1.62.94l.36 2.54c.05.24.26.42.5.42h4c.25 0 .46-.18.49-.42l.36-2.54c.59-.24 1.13-.57 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32a.49.49 0 00-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z" />
          </svg>
        </button>
      </div>
    </header>
  );
}
