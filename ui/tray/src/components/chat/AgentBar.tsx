import { useState, useRef, useEffect } from "react";
import { useChatStore } from "../../stores/chat";
import { useSettingsStore } from "../../stores/settings";
import { useSystemStore } from "../../stores/system";
import { AGENTS, type AgentId } from "../../api/types";

const AGENT_ICONS: Record<AgentId, string> = {
  auto: "hive",
  general: "auto_awesome",
  thesis: "menu_book",
  code: "code",
  calendar: "calendar_month",
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

export default function AgentBar() {
  const [open, setOpen] = useState(false);
  const { activeAgent, setActiveAgent } = useChatStore();
  const status = useSystemStore((s) => s.status);
  const ref = useRef<HTMLDivElement>(null);

  const engineOk = status?.engine_ok ?? false;
  const settingsModel = useSettingsStore.getState().activeModel;
  const runningModel = status?.current_model_id ?? status?.model ?? null;
  const model = engineOk ? (runningModel || settingsModel || "local") : "—";
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
    <div className="flex items-center justify-between mb-2 px-1" ref={ref}>
      <div className="relative">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-container/50 border border-outline-variant/20 hover:bg-surface-container transition-colors"
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          <span className={`material-symbols-outlined text-[18px] ${AGENT_COLORS[currentAgent.id]}`}>
            {AGENT_ICONS[currentAgent.id]}
          </span>
          <span className="text-sm font-medium text-on-surface">{currentAgent.label}</span>
          <span className={`material-symbols-outlined text-[16px] text-on-surface-variant transition-transform ${open ? "rotate-180" : ""}`}>
            expand_more
          </span>
        </button>

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
                    ? "bg-surface-container"
                    : "hover:bg-surface-container"
                }`}
              >
                <span className={`material-symbols-outlined text-[18px] p-1 rounded-md ${AGENT_BG[agent.id]} ${AGENT_COLORS[agent.id]}`}>
                  {AGENT_ICONS[agent.id]}
                </span>
                <span className="flex flex-col">
                  <span className="text-[13px] text-on-surface font-semibold leading-tight">
                    {agent.label}
                  </span>
                  <span className="text-[11px] text-outline leading-tight">{agent.description}</span>
                </span>
                {agent.id === activeAgent && (
                  <span className="ml-auto material-symbols-outlined text-[16px] text-primary-container">check</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="text-xs text-on-surface-variant/60 font-label-mono truncate max-w-[200px]">
        {model}
      </div>
    </div>
  );
}
