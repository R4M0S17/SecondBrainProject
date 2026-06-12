import { useEffect, useMemo } from "react";
import { useToolsStore } from "../../stores/tools";
import { useChatStore } from "../../stores/chat";
import { useSystemStore } from "../../stores/system";

const SCOPE_COLORS: Record<string, string> = {
  local: "bg-surface-container",
  sandboxed: "bg-[#1e2a1e]",
  restricted: "bg-[#2a1e1e]",
};

const SCOPE_LABELS: Record<string, string> = {
  local: "Local",
  sandboxed: "Sandbox",
  restricted: "Restricted",
};

const QUICK_ACTIONS = [
  {
    id: "search-files",
    label: "Buscar archivo",
    icon: "search",
    description: "Buscar archivos por nombre o contenido",
  },
  {
    id: "create-note",
    label: "Crear nota",
    icon: "note_add",
    description: "Crear nota en Apple Notes",
  },
  {
    id: "run-workflow",
    label: "Ejecutar workflow",
    icon: "play_arrow",
    description: "Ejecutar workflow de automatización",
  },
  {
    id: "search-web",
    label: "Buscar en web",
    icon: "language",
    description: "Buscar información actual en internet",
  },
  {
    id: "calendar-events",
    label: "Eventos del día",
    icon: "calendar_month",
    description: "Listar eventos del calendario",
  },
  {
    id: "spotlight",
    label: "Spotlight",
    icon: "lightbulb",
    description: "Buscar con Spotlight en macOS",
  },
];

export default function ToolsPanel() {
  const { tools, loading, error, load, toggleTool } = useToolsStore();
  const messages = useChatStore((s) => s.messages);
  const status = useSystemStore((s) => s.status);

  useEffect(() => {
    load();
  }, [load]);

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
        Tool Manager
      </h2>

      {error && (
        <div className="bg-[#2a1e1e] border border-[#4a2e2e] text-error px-3 py-2 rounded text-[12px] mb-3">
          {error}
        </div>
      )}

      {loading && tools.length === 0 ? (
        <div className="flex items-center justify-center flex-1 text-outline text-[13px]">
          Loading tools...
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto custom-scrollbar space-y-5 pr-1">
          {/* ── Tool Browser ── */}
          <section>
            <h3 className="text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2 flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[14px]">construction</span>
              Tool Browser
            </h3>
            {Object.entries(groupedTools).map(([category, cats]) => (
              <div key={category} className="mb-3">
                <h4 className="text-[10px] font-bold tracking-[0.1em] text-on-surface-variant uppercase mb-1.5 px-1">
                  {category}
                </h4>
                <div className="space-y-[1px]">
                  {cats.map((t) => (
                    <div
                      key={t.name}
                      className="flex items-center justify-between px-2.5 py-1.5 rounded hover:bg-surface-container-low transition-colors"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="font-mono text-[12px] text-on-surface truncate">
                          {t.name}
                        </span>
                        <div className="flex items-center gap-1">
                          <span
                            className={`text-[9px] px-1 rounded leading-[14px] ${
                              SCOPE_COLORS[t.scope] || "bg-surface-container"
                            } text-on-surface-variant font-medium`}
                            title={`Scope: ${SCOPE_LABELS[t.scope] || t.scope}`}
                          >
                            {SCOPE_LABELS[t.scope] || t.scope}
                          </span>
                          {t.requires_confirmation && (
                            <span
                              className="text-[9px] px-1 rounded bg-[#2a2a1e] text-yellow-500 font-medium"
                              title="Requires user confirmation"
                            >
                              Confirm
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => toggleTool(t.name, !t.enabled)}
                          role="switch"
                          aria-checked={t.enabled}
                          className={`w-7 h-3.5 rounded-full relative cursor-pointer transition-colors shrink-0 ${
                            t.enabled ? "bg-primary-container" : "bg-surface-container-highest"
                          }`}
                        >
                          <div
                            className={`absolute top-[1px] w-[10px] h-[10px] bg-white rounded-full transition-transform ${
                              t.enabled ? "translate-x-[14px]" : "translate-x-[1px]"
                            }`}
                          />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </section>

          {/* ── Recent Usage ── */}
          {toolUsage.length > 0 && (
            <section>
              <h3 className="text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2 flex items-center gap-1.5">
                <span className="material-symbols-outlined text-[14px]">history</span>
                Recent Usage
                <span className="text-[10px] text-on-surface-variant font-normal normal-case ml-1">
                  ({status?.tool_call_count ?? 0} total calls)
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
                        {(totalLatency / count / 1000).toFixed(1)}s avg
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
              Quick Actions
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {QUICK_ACTIONS.map((action) => (
                <button
                  key={action.id}
                  className="flex items-center gap-2 px-3 py-2.5 bg-surface-container-low hover:bg-surface-container border border-outline-variant/30 rounded-lg transition-colors text-left group"
                  title={action.description}
                >
                  <span className="material-symbols-outlined text-[18px] text-primary-container group-hover:scale-110 transition-transform">
                    {action.icon}
                  </span>
                  <div className="min-w-0">
                    <div className="text-[12px] font-medium text-on-surface truncate">
                      {action.label}
                    </div>
                    <div className="text-[10px] text-on-surface-variant truncate">
                      {action.description}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
