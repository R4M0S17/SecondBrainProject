import { useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useToolsStore } from "../../../stores/tools";
import ToggleSwitch from "../../shared/ToggleSwitch";

const SCOPE_COLORS: Record<string, string> = {
  local: "bg-surface-container",
  sandboxed: "bg-[#1e2a1e]",
  restricted: "bg-[#2a1e1e]",
};

const RECENT_USAGE = [
  { name: "read_file", count: 42 },
  { name: "write_file", count: 18 },
  { name: "execute_python", count: 12 },
];

export default function ToolManagerSection() {
  const { t } = useTranslation();
  const { tools, loading: toolsLoading, load: loadTools, toggleTool } = useToolsStore();
  const toolRetryRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    loadTools();
    return () => { if (toolRetryRef.current) clearTimeout(toolRetryRef.current); };
  }, [loadTools]);

  useEffect(() => {
    if (!toolsLoading && tools.length === 0) {
      toolRetryRef.current = setTimeout(loadTools, 2000);
    }
  }, [toolsLoading, tools.length, loadTools]);

  const groupedTools = useMemo(() => {
    const groups: Record<string, typeof tools> = {};
    for (const tool of tools) {
      const category = tool.required_permission.split(".")[1] || "other";
      if (!groups[category]) groups[category] = [];
      groups[category].push(tool);
    }
    return groups;
  }, [tools]);

  const totalEnabled = tools.filter((t) => t.enabled).length;

  return (
    <div className="max-w-2xl space-y-8">
      {/* Header stats */}
      <div className="flex items-center gap-4">
        <div className="text-[13px] text-on-surface-variant">
          {t("tools.browser")}
          <span className="ml-2 text-[11px] text-outline">
            ({totalEnabled}/{tools.length} {t("tools.manager").toLowerCase()})
          </span>
        </div>
      </div>

      {/* Tool browser */}
      {toolsLoading && tools.length === 0 ? (
        <p className="text-[13px] text-outline">{t("tools.loading")}</p>
      ) : tools.length === 0 ? (
        <p className="text-[13px] text-outline">{t("tools.no_tools_ready")}</p>
      ) : (
        <div className="space-y-6">
          {Object.entries(groupedTools).map(([category, cats]) => {
            const catEnabled = cats.filter((t) => t.enabled).length;
            return (
              <div key={category}>
                <h4 className="text-[10px] font-bold tracking-[0.1em] text-on-surface-variant uppercase mb-2 px-1">
                  {category}
                  <span className="ml-2 font-normal text-outline text-[9px] tracking-normal">
                    ({catEnabled}/{cats.length} {t("tools.manager").toLowerCase()})
                  </span>
                </h4>
                <div className="space-y-[1px]">
                  {cats.map((tool) => (
                    <div
                      key={tool.name}
                      className="flex items-center justify-between px-3 py-2 rounded hover:bg-surface-container-low transition-colors group"
                      title={tool.description || undefined}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="font-mono text-[12px] text-on-surface truncate">
                          {tool.name}
                        </span>
                        <span
                          className={`text-[9px] px-1.5 rounded leading-[14px] ${SCOPE_COLORS[tool.scope] || "bg-surface-container"} text-on-surface-variant font-medium shrink-0`}
                        >
                          {t(`tools.scope_${tool.scope}`, { defaultValue: tool.scope })}
                        </span>
                        {tool.requires_confirmation && (
                          <span className="text-[9px] px-1.5 rounded bg-[#2a2a1e] text-yellow-500 font-medium shrink-0">
                            {t("tools.confirm")}
                          </span>
                        )}
                        {tool.description && (
                          <span className="text-[10px] text-outline hidden group-hover:inline truncate max-w-[200px]">
                            {tool.description}
                          </span>
                        )}
                      </div>
                      <ToggleSwitch
                        enabled={tool.enabled}
                        onChange={(v) => toggleTool(tool.name, v)}
                        size="sm"
                        ariaLabel={t("tools.toggle_tool", { name: tool.name })}
                        className="bg-surface-container-highest shrink-0 ml-2"
                      />
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Recent Usage */}
      <section>
        <h4 className="text-[10px] font-bold tracking-[0.1em] text-on-surface-variant uppercase mb-3">
          {t("tools.recent_usage")}
        </h4>
        <div className="space-y-1">
          {RECENT_USAGE.map((item) => (
            <div
              key={item.name}
              className="flex items-center justify-between px-3 py-1.5 rounded bg-surface-container-low"
            >
              <span className="font-mono text-[12px] text-on-surface">{item.name}</span>
              <span className="text-[11px] text-outline">
                {t("tools.total_calls", { count: item.count })}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
