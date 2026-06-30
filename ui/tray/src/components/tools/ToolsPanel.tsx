import { useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useToolsStore } from "../../stores/tools";
import { useChatStore } from "../../stores/chat";
import { useSystemStore } from "../../stores/system";
import { useDashboardStore } from "../../stores/dashboard";
import ToggleSwitch from "../shared/ToggleSwitch";

const SCOPE_COLORS: Record<string, string> = {
  local: "bg-surface-container",
  sandboxed: "bg-[#1e2a1e]",
  restricted: "bg-[#2a1e1e]",
};

const QUICK_ACTIONS = [
  {
    id: "search-files",
    labelKey: "tools.search_files",
    icon: "search",
    descKey: "tools.search_files_desc",
  },
  {
    id: "create-note",
    labelKey: "tools.create_note",
    icon: "note_add",
    descKey: "tools.create_note_desc",
  },
  {
    id: "run-workflow",
    labelKey: "tools.run_workflow",
    icon: "play_arrow",
    descKey: "tools.run_workflow_desc",
  },
  {
    id: "search-web",
    labelKey: "tools.search_web",
    icon: "language",
    descKey: "tools.search_web_desc",
  },
  {
    id: "calendar-events",
    labelKey: "tools.day_events",
    icon: "calendar_month",
    descKey: "tools.day_events_desc",
  },
  {
    id: "spotlight",
    labelKey: "tools.spotlight",
    icon: "lightbulb",
    descKey: "tools.spotlight_desc",
  },
];

export default function ToolsPanel() {
  const { t } = useTranslation();
  const { tools, loading, error, load, toggleTool } = useToolsStore();
  const messages = useChatStore((s) => s.messages);
  const status = useSystemStore((s) => s.status);
  const setSearchDocsOpen = useDashboardStore((s) => s.setSearchDocsOpen);
  const retryRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    load();
    return () => { if (retryRef.current) clearTimeout(retryRef.current); };
  }, [load]);

  useEffect(() => {
    if (!loading && tools.length === 0 && !error) {
      retryRef.current = setTimeout(load, 2000);
    }
  }, [loading, tools.length, error, load]);

  const toolUsage = useMemo(() => {
    const counts: Record<string, { count: number; totalLatency: number }> = {};
    for (const msg of messages) {
      if (msg.metadata?.tools_called) {
        for (const tc of msg.metadata.tools_called) {
          if (!counts[tc.name]) counts[tc.name] = { count: 0, totalLatency: 0 };
          counts[tc.name].count++;
          counts[tc.name].totalLatency += tc.latency_ms;
        }
      }
    }
    return Object.entries(counts)
      .map(([name, data]) => ({ name, ...data }))
      .sort((a, b) => b.count - a.count);
  }, [messages]);

  const groupedTools = useMemo(() => {
    const groups: Record<string, typeof tools> = {};
    for (const t of tools) {
      const category = t.required_permission.split(".")[1] || "other";
      if (!groups[category]) groups[category] = [];
      groups[category].push(t);
    }
    return groups;
  }, [tools]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden px-4 md:px-6 lg:px-8 pt-4 pb-6 w-full min-w-0">
      <h2 className="text-[15px] font-semibold text-on-surface mb-4">
        {t("tools.manager")}
      </h2>

      {error && (
        <div className="bg-[#2a1e1e] border border-[#4a2e2e] text-error px-3 py-2 rounded text-[12px] mb-3">
          {error}
        </div>
      )}

      {loading && tools.length === 0 ? (
        <div className="flex items-center justify-center flex-1 text-outline text-[13px]">
          {t("tools.loading")}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto custom-scrollbar space-y-5 pr-1">
          {/* ── Tool Browser ── */}
          <section>
            <h3 className="text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2 flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[14px]">construction</span>
              {t("tools.browser")}
            </h3>
            {tools.length === 0 && !loading ? (
              <div className="p-3 rounded-lg border border-outline-variant/20 bg-surface-container/30 opacity-70 flex items-center justify-center">
                <span className="text-xs text-outline">{t("tools.no_tools_ready")}</span>
              </div>
            ) : (
              Object.entries(groupedTools).map(([category, cats]) => (
                <div key={category} className="mb-3">
                  <h4 className="text-[10px] font-bold tracking-[0.1em] text-on-surface-variant uppercase mb-1.5 px-1">
                    {category}
                  </h4>
                  <div className="space-y-[1px]">
                    {cats.map((tool) => (
                      <div
                        key={tool.name}
                        className="flex items-center justify-between px-2.5 py-1.5 rounded hover:bg-surface-container-low transition-colors"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="font-mono text-[12px] text-on-surface truncate">
                            {tool.name}
                          </span>
                          <div className="flex items-center gap-1">
                            <span
                              className={`text-[9px] px-1 rounded leading-[14px] ${
                                SCOPE_COLORS[tool.scope] || "bg-surface-container"
                              } text-on-surface-variant font-medium`}
                              title={t("tools.scope_label", { scope: t(`tools.scope_${tool.scope}`, { defaultValue: tool.scope }) })}
                            >
                              {t(`tools.scope_${tool.scope}`, { defaultValue: tool.scope })}
                            </span>
                            {tool.requires_confirmation && (
                              <span
                                className="text-[9px] px-1 rounded bg-[#2a2a1e] text-yellow-500 font-medium"
                                title={t("tools.requires_confirmation")}
                              >
                                {t("tools.confirm")}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <ToggleSwitch
                            enabled={tool.enabled}
                            onChange={(v) => toggleTool(tool.name, v)}
                            size="sm"
                            ariaLabel={t("tools.toggle_tool", { name: tool.name })}
                            className="bg-surface-container-highest"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </section>

          {/* ── Recent Usage ── */}
          {toolUsage.length > 0 && (
            <section>
              <h3 className="text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2 flex items-center gap-1.5">
                <span className="material-symbols-outlined text-[14px]">history</span>
                {t("tools.recent_usage")}
                <span className="text-[10px] text-on-surface-variant font-normal normal-case ml-1">
                  {t("tools.total_calls", { count: status?.tool_call_count ?? 0 })}
                </span>
              </h3>
              <div className="space-y-[1px]">
                {toolUsage.slice(0, 15).map(({ name, count, totalLatency }) => (
                  <div
                    key={name}
                    className="flex items-center justify-between px-2.5 py-1.5 rounded hover:bg-surface-container-low transition-colors"
                  >
                    <span className="font-mono text-[12px] text-on-surface">{name}</span>
                    <div className="flex items-center gap-3 text-[11px] text-on-surface-variant">
                      <span>{count}x</span>
                      <span className="font-mono">
                        {t("tools.s_avg", { seconds: (totalLatency / count / 1000).toFixed(1) })}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ── Manual Shortcuts ── */}
          <section>
            <h3 className="text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2 flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[14px]">quick_reference</span>
              {t("tools.quick_actions")}
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {QUICK_ACTIONS.map((action) => {
                const handleClick = action.id === "search-files"
                  ? () => setSearchDocsOpen(true)
                  : undefined;
                return (
                <button
                  key={action.id}
                  onClick={handleClick}
                  className="flex items-center gap-2 px-3 py-2.5 bg-surface-container-low hover:bg-surface-container border border-outline-variant/30 rounded-lg transition-colors text-left group"
                  title={t(action.descKey)}
                >
                  <span className="material-symbols-outlined text-[18px] text-primary-container group-hover:scale-110 transition-transform">
                    {action.icon}
                  </span>
                  <div className="min-w-0">
                    <div className="text-[12px] font-medium text-on-surface truncate">
                      {t(action.labelKey)}
                    </div>
                    <div className="text-[10px] text-on-surface-variant truncate">
                      {t(action.descKey)}
                    </div>
                  </div>
                </button>
                );
              })}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
