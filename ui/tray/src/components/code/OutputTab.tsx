import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useToolOutputStore } from "../../stores/toolOutput";

const FORMATTED_NAMES: Record<string, string> = {
  execute_python: "Python",
  run_script: "Shell Script",
  write_file: "Write File",
  read_file: "Read File",
  search_web: "Web Search",
  create_calendar_event: "Calendar Event",
  add_reminder: "Reminder",
  delete_reminder: "Delete Reminder",
  delete_file: "Delete File",
};

function toolDisplayName(name: string): string {
  return FORMATTED_NAMES[name] ?? name.replace(/_/g, " ");
}

function formatTs(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function OutputTab() {
  const { t } = useTranslation();
  const calls = useToolOutputStore((s) => s.calls);
  const clearAll = useToolOutputStore((s) => s.clear);

  const [filter, setFilter] = useState<"all" | "approved" | "denied">("all");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggleExpand = (key: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  const filtered = calls
    .filter((tc) => filter === "all" || (filter === "approved" ? tc.approved : !tc.approved))
    .filter((tc) => !search || tc.name.toLowerCase().includes(search.toLowerCase()))
    .slice()
    .reverse();

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[11px] text-on-surface-variant/60 flex items-center gap-1.5">
          <span className="material-symbols-outlined text-[14px] text-primary-container/60">info</span>
          {t("output.tools_executed")}
        </p>
        {calls.length > 0 && (
          <button
            onClick={clearAll}
            className="flex items-center gap-1 px-2 py-1 text-[10px] text-outline/50 hover:text-on-surface-variant rounded-md hover:bg-surface-container-low transition-colors"
          >
            <span className="material-symbols-outlined text-[12px]">delete_sweep</span>
            {t("output.clear_history")}
          </button>
        )}
      </div>

      {calls.length > 0 && (
        <div className="flex items-center gap-2 mb-4">
          <div className="flex-1 relative">
            <span className="material-symbols-outlined text-[14px] text-outline/40 absolute left-2.5 top-1/2 -translate-y-1/2">
              search
            </span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("output.search_placeholder")}
              className="w-full bg-surface-container-low border border-outline-variant/15 rounded-lg pl-8 pr-3 py-1.5 text-[12px] text-on-surface placeholder-outline/30 outline-none focus:border-primary-container/40 transition-colors"
            />
          </div>
          {(["all", "approved", "denied"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 text-[11px] font-medium rounded-lg transition-colors whitespace-nowrap ${
                filter === f
                  ? "bg-primary-container/10 text-primary-container"
                  : "text-outline/50 hover:text-on-surface"
              }`}
            >
              {t(`output.filter_${f}`)}
            </button>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-y-auto custom-scrollbar pr-1">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-outline">
            <span className="material-symbols-outlined text-[40px] text-outline/30">output</span>
            <p className="text-[13px]">{calls.length === 0 ? t("output.no_tools") : t("output.no_result")}</p>
            <p className="text-[11px] text-outline/60 text-center max-w-sm">
              {calls.length === 0 ? t("output.no_tools_desc") : ""}
            </p>
          </div>
        ) : (
          <div className="relative pl-6">
            <div className="absolute left-2 top-0 bottom-0 w-px bg-outline-variant/15" />
            {filtered.map((tc) => {
              const cardKey = tc.id;
              const isExpanded = expanded.has(cardKey);
              return (
                <div key={cardKey} className="relative mb-3">
                  <div className={`absolute -left-4 top-3.5 w-2 h-2 rounded-full border-2 ${
                    tc.approved
                      ? "bg-[#4ade80] border-[#1a2e1a]"
                      : "bg-[#f87171] border-[#2a1e1e]"
                  }`} />
                  <div className="bg-surface-container-low border border-outline-variant/10 rounded-xl p-4 hover:border-outline-variant/25 transition-colors">
                  <div className="flex items-center justify-between mb-2.5">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-primary-container/10 text-primary-container font-mono">
                        {toolDisplayName(tc.name)}
                      </span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                        tc.approved
                          ? "bg-[#1a2e1a] text-[#4ade80]"
                          : "bg-[#2a1e1e] text-[#f87171]"
                      }`}>
                        {tc.approved ? t("output.executed") : t("output.denied")}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      {tc.timestamp && (
                        <span className="text-[10px] text-outline/40 font-label-mono">
                          {formatTs(tc.timestamp)}
                        </span>
                      )}
                      <span className="text-[10px] text-outline/50 font-label-mono">
                        {tc.latency_ms}ms
                      </span>
                    </div>
                  </div>
                  {tc.args_summary && tc.args_summary !== "{}" && (
                    <div className="mb-2">
                      <div className="text-[9px] text-outline/50 uppercase tracking-wider font-bold mb-1">
                        {t("output.arguments")}
                      </div>
                      <pre className="text-[11px] text-on-surface-variant/80 font-mono whitespace-pre-wrap bg-surface-container-lowest/50 rounded-lg p-2.5 border border-outline-variant/5">
                        {tc.args_summary}
                      </pre>
                    </div>
                  )}
                  <div>
                    <div className="text-[9px] text-outline/50 uppercase tracking-wider font-bold mb-1">
                      {t("output.result")}
                    </div>
                    <div className="relative">
                      <pre
                        className={`text-[12px] text-on-surface font-mono whitespace-pre-wrap bg-surface-container-lowest/50 rounded-lg p-2.5 border border-outline-variant/5 leading-relaxed transition-all ${
                          isExpanded ? "" : "max-h-40 overflow-hidden"
                        }`}
                      >
                        {tc.result_summary || (
                          <span className="text-on-surface-variant/40 italic">{t("output.no_result")}</span>
                        )}
                      </pre>
                      {(tc.result_summary?.length ?? 0) > 300 && (
                        <button
                          onClick={() => toggleExpand(cardKey)}
                          className="mt-1 text-[10px] text-primary-container/70 hover:text-primary-container flex items-center gap-1 transition-colors"
                        >
                          <span className="material-symbols-outlined text-[13px]">
                            {isExpanded ? "expand_less" : "expand_more"}
                          </span>
                          {isExpanded ? t("output.collapse") : t("output.expand")}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
