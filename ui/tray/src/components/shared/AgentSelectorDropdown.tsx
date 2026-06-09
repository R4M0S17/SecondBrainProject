import { useState, useRef, useEffect } from "react";
import { useChatStore } from "../../stores/chat";
import { useSettingsStore } from "../../stores/settings";
import { useSystemStore } from "../../stores/system";
import { AGENTS, type AgentId } from "../../api/types";

const AGENT_ICONS: Record<AgentId, JSX.Element> = {
  auto: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <circle cx="5" cy="6" r="2" fill="currentColor" stroke="none" opacity={0.35} />
      <circle cx="19" cy="6" r="2" fill="currentColor" stroke="none" opacity={0.35} />
      <circle cx="12" cy="18" r="2" fill="currentColor" stroke="none" opacity={0.35} />
      <path d="M7 7.5l5 4.5M17 7.5l-5 4.5M12 12v4" />
    </svg>
  ),
  general: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z" fill="currentColor" stroke="none" opacity={0.25}/>
      <path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z"/>
      <path d="M19 17l.5 1.5 1.5.5-1.5.5-.5 1.5-.5-1.5L17 19l1.5-.5.5-1.5z"/>
    </svg>
  ),
  thesis: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" fill="currentColor" stroke="none" opacity={0.15}/>
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
      <line x1="9" y1="7" x2="15" y2="7"/>
      <line x1="9" y1="11" x2="15" y2="11"/>
    </svg>
  ),
  code: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <rect x="2" y="3" width="20" height="14" rx="2" fill="currentColor" stroke="none" opacity={0.15}/>
      <rect x="2" y="3" width="20" height="14" rx="2"/>
      <polyline points="8 10 5 13 8 16"/>
      <polyline points="16 10 19 13 16 16"/>
      <line x1="12" y1="9" x2="12" y2="17"/>
    </svg>
  ),
  calendar: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <rect x="3" y="4" width="18" height="18" rx="2" fill="currentColor" stroke="none" opacity={0.15}/>
      <rect x="3" y="4" width="18" height="18" rx="2"/>
      <line x1="16" y1="2" x2="16" y2="6"/>
      <line x1="8" y1="2" x2="8" y2="6"/>
      <line x1="3" y1="10" x2="21" y2="10"/>
      <circle cx="8" cy="15" r="1" fill="currentColor" stroke="none"/>
      <circle cx="12" cy="15" r="1" fill="currentColor" stroke="none"/>
      <circle cx="16" cy="15" r="1" fill="currentColor" stroke="none"/>
    </svg>
  ),
};

const AGENT_COLORS: Record<AgentId, string> = {
  auto:     "text-cyan-400",
  general: "text-violet-400",
  thesis:  "text-amber-400",
  code:    "text-emerald-400",
  calendar:"text-sky-400",
};

const AGENT_BG: Record<AgentId, string> = {
  auto:     "bg-cyan-500/10",
  general: "bg-violet-500/10",
  thesis:  "bg-amber-500/10",
  code:    "bg-emerald-500/10",
  calendar:"bg-sky-500/10",
};

export default function AgentSelectorDropdown() {
  const [open, setOpen] = useState(false);
  const { activeAgent, setActiveAgent } = useChatStore();
  const { status } = useSystemStore();
  const ref = useRef<HTMLDivElement>(null);

  const settingsModel = useSettingsStore.getState().activeModel;
  const model = status?.current_model_id ?? settingsModel ?? status?.model ?? "—";
  const currentAgent = AGENTS.find((a) => a.id === activeAgent) ?? AGENTS[0];

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const select = (id: AgentId) => {
    setActiveAgent(id);
    setOpen(false);
  };

  return (
    <div className="relative" ref={ref}>
      {/* Trigger */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1.5 cursor-pointer hover:bg-surface-container-highest transition-colors px-1.5 py-[2px] rounded"
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          <span className={`${AGENT_COLORS[currentAgent.id]}`}>
            {AGENT_ICONS[currentAgent.id]}
          </span>
          <span className="text-[13px] text-[#e8eaf0] font-semibold">
            {currentAgent.label}
          </span>
          <svg
            className={`w-3.5 h-3.5 text-on-surface-variant transition-transform ${open ? "rotate-180" : ""}`}
            viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>

        {/* Model badge */}
        <div className="bg-surface-container-highest text-on-surface-variant text-[11px] font-bold tracking-[0.05em] px-2 py-[1px] rounded-full flex items-center">
          {model}
        </div>
      </div>

      {/* Dropdown */}
      {open && (
        <div
          role="listbox"
          className="absolute top-full left-0 mt-1 w-[240px] bg-surface-container-low border border-outline-variant rounded-lg shadow-xl z-50 overflow-hidden p-1 flex flex-col gap-0.5"
        >
          {AGENTS.map((agent) => (
            <button
              key={agent.id}
              role="option"
              aria-selected={agent.id === activeAgent}
              onClick={() => select(agent.id)}
              className={`w-full text-left px-3 py-2 flex items-center gap-3 rounded-md transition-colors ${
                agent.id === activeAgent
                  ? "bg-[#27263080]"
                  : "hover:bg-surface-container"
              }`}
            >
              <span className={`flex-shrink-0 p-1.5 rounded-md ${AGENT_BG[agent.id]} ${AGENT_COLORS[agent.id]}`}>
                {AGENT_ICONS[agent.id]}
              </span>
              <span className="flex flex-col">
                <span className="text-[13px] text-[#e8eaf0] font-semibold leading-tight">
                  {agent.label}
                </span>
                <span className="text-[11px] text-outline leading-tight">{agent.description}</span>
              </span>
              {agent.id === activeAgent && (
                <svg className="ml-auto w-3.5 h-3.5 text-primary-container flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
