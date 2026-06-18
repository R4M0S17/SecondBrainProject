import { useChatStore } from "../../stores/chat";
import type { ToolCallRecord } from "../../api/types";

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

export default function OutputTab() {
  const messages = useChatStore((s) => s.messages);

  const toolCalls: (ToolCallRecord & { msgIdx: number; tcIdx: number })[] = [];
  for (const msg of messages) {
    if (msg.metadata?.tools_called) {
      for (let tci = 0; tci < msg.metadata.tools_called.length; tci++) {
        const tc = msg.metadata.tools_called[tci];
        toolCalls.push({ ...tc, msgIdx: toolCalls.length, tcIdx: tci });
      }
    }
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <p className="text-[11px] text-on-surface-variant/60 mb-4 flex items-center gap-1.5">
        <span className="material-symbols-outlined text-[14px] text-primary-container/60">info</span>
        Resultados de herramientas ejecutadas
      </p>
      <div className="flex-1 overflow-y-auto custom-scrollbar pr-1">
        {toolCalls.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-outline">
            <span className="material-symbols-outlined text-[40px] text-outline/30">output</span>
            <p className="text-[13px]">No tools executed yet</p>
            <p className="text-[11px] text-outline/60 text-center max-w-sm">
              Ask the agent to run scripts, search files, or perform tasks. Results will appear here.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {toolCalls
              .slice()
              .reverse()
              .map((tc) => (
                <div
                  key={`${tc.msgIdx}-${tc.tcIdx}`}
                  className="bg-surface-container-low border border-outline-variant/10 rounded-xl p-4 hover:border-outline-variant/25 transition-colors"
                >
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
                        {tc.approved ? "Executed" : "Denied"}
                      </span>
                    </div>
                    <span className="text-[10px] text-outline/50 font-label-mono">
                      {tc.latency_ms}ms
                    </span>
                  </div>
                  {tc.args_summary && tc.args_summary !== "{}" && (
                    <div className="mb-2">
                      <div className="text-[9px] text-outline/50 uppercase tracking-wider font-bold mb-1">
                        Argumentos
                      </div>
                      <pre className="text-[11px] text-on-surface-variant/80 font-mono whitespace-pre-wrap bg-surface-container-lowest/50 rounded-lg p-2.5 border border-outline-variant/5">
                        {tc.args_summary}
                      </pre>
                    </div>
                  )}
                  <div>
                    <div className="text-[9px] text-outline/50 uppercase tracking-wider font-bold mb-1">
                      Resultado
                    </div>
                    <pre className="text-[12px] text-on-surface font-mono whitespace-pre-wrap max-h-40 overflow-y-auto bg-surface-container-lowest/50 rounded-lg p-2.5 border border-outline-variant/5 leading-relaxed">
                      {tc.result_summary || (
                        <span className="text-on-surface-variant/40 italic">No result</span>
                      )}
                    </pre>
                  </div>
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
