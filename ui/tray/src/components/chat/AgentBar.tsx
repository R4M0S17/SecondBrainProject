import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useChatStore } from "../../stores/chat";
import { useSettingsStore } from "../../stores/settings";
import { useSystemStore } from "../../stores/system";
import { AGENTS, type AgentId } from "../../api/types";

const BASIC_AGENTS: AgentId[] = ["auto", "general"];
const ADVANCED_AGENTS: AgentId[] = ["thesis", "code", "calendar"];

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
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const { activeAgent, setActiveAgent, conversationTitle, renameConversation } = useChatStore();
  const status = useSystemStore((s) => s.status);
  const ref = useRef<HTMLDivElement>(null);
  const titleInputRef = useRef<HTMLInputElement>(null);

  const engineOk = status?.engine_ok ?? false;
  const settingsModel = useSettingsStore.getState().activeModel;
  const runningModel = status?.current_model_id ?? status?.model ?? null;
  const model = engineOk ? (runningModel || settingsModel || "local") : "—";
  const currentAgent = AGENTS.find((a) => a.id === activeAgent) ?? AGENTS[0];

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setShowAdvanced(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    if (editingTitle && titleInputRef.current) {
      titleInputRef.current.focus();
      titleInputRef.current.select();
    }
  }, [editingTitle]);

  const clearMessages = useChatStore((s) => s.clearMessages);

  const select = (id: AgentId) => {
    setActiveAgent(id);
    setOpen(false);
    setShowAdvanced(false);
  };

  const renderAgent = (agent: typeof AGENTS[0]) => (
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
  );

  const startEditing = () => {
    setTitleDraft(conversationTitle || "");
    setEditingTitle(true);
  };

  const commitTitle = () => {
    const trimmed = titleDraft.trim();
    if (trimmed) renameConversation(trimmed);
    setEditingTitle(false);
  };

  const cancelEditing = () => {
    setEditingTitle(false);
  };

  return (
    <div ref={ref}>
      <div className="flex items-center justify-between mb-1 px-1">
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
              {AGENTS.filter((a) => BASIC_AGENTS.includes(a.id)).map(renderAgent)}

              {BASIC_AGENTS.includes(activeAgent) && ADVANCED_AGENTS.includes(activeAgent) && (
                <hr className="border-outline-variant/20 my-1" />
              )}

              {ADVANCED_AGENTS.some((id) => {
                const agent = AGENTS.find((a) => a.id === id);
                return agent && (agent.id === activeAgent || showAdvanced);
              }) ? (
                <>
                  {showAdvanced && (
                    <>
                      <div className="px-3 py-1">
                        <span className="text-[10px] font-bold tracking-[0.05em] text-outline uppercase">
                          {t("chat.advanced_agents")}
                        </span>
                      </div>
                      {AGENTS.filter((a) => ADVANCED_AGENTS.includes(a.id)).map(renderAgent)}
                    </>
                  )}
                  <button
                    onClick={() => setShowAdvanced((v) => !v)}
                    className="w-full text-left px-3 py-1.5 flex items-center gap-2 rounded-md text-[11px] text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors"
                  >
                    <span className="material-symbols-outlined text-[14px]">
                      {showAdvanced ? "expand_less" : "expand_more"}
                    </span>
                    {showAdvanced ? t("chat.hide_advanced") : t("chat.show_advanced")}
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setShowAdvanced(true)}
                  className="w-full text-left px-3 py-1.5 flex items-center gap-2 rounded-md text-[11px] text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors"
                >
                  <span className="material-symbols-outlined text-[14px]">expand_more</span>
                  {t("chat.show_advanced")}
                </button>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => clearMessages()}
            title={t("chat.clear")}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-xs text-on-surface-variant/50 hover:text-error hover:bg-error/10 transition-colors"
          >
            <span className="material-symbols-outlined text-[16px]">delete</span>
            {t("chat.clear")}
          </button>
          <div className="text-xs text-on-surface-variant/60 font-label-mono truncate max-w-[140px]">
            {model}
          </div>
        </div>
      </div>

      {editingTitle ? (
        <div className="px-1 mb-2 flex items-center gap-1">
          <input
            ref={titleInputRef}
            type="text"
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitTitle();
              if (e.key === "Escape") cancelEditing();
            }}
            onBlur={commitTitle}
            className="flex-1 bg-surface-container-low border border-outline-variant/50 rounded px-2 py-1 text-xs text-on-surface outline-none focus:border-primary-container"
            placeholder={t("chat.title_placeholder")}
            maxLength={100}
          />
        </div>
      ) : conversationTitle ? (
        <button
          onClick={startEditing}
          className="mb-2 px-2 py-0.5 w-full text-left group flex items-center gap-1.5"
          title={t("chat.rename")}
        >
          <span className="text-[12px] text-on-surface-variant/80 truncate font-medium">
            {conversationTitle}
          </span>
          <span className="material-symbols-outlined text-[12px] text-outline/40 opacity-0 group-hover:opacity-100 transition-opacity">edit</span>
        </button>
      ) : null}
    </div>
  );
}
