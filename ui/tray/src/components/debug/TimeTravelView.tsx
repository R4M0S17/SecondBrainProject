import { useEffect, useCallback } from "react";
import { useDebugStore } from "../../stores/debug";

const NODE_COLORS: Record<string, string> = {
  context_assembly: "#6366f1",
  fast_path: "#22c55e",
  reason_node: "#f59e0b",
  tool_node: "#ef4444",
  observe_node: "#3b82f6",
  update_state: "#8b5cf6",
};

export default function TimeTravelView({ onClose }: { onClose: () => void }) {
  const {
    runs,
    selectedRunId,
    steps,
    selectedStep,
    isLoading,
    error,
    loadRuns,
    selectRun,
    selectStep,
  } = useDebugStore();

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  const handleRunClick = useCallback(
    (id: string) => {
      selectRun(id);
    },
    [selectRun]
  );

  const handleStepClick = useCallback(
    (stepId: string) => {
      selectStep(stepId);
    },
    [selectStep]
  );

  return (
    <div className="fixed inset-0 z-50 flex bg-black/60 backdrop-blur-sm">
      <div className="flex flex-col w-full h-full bg-background text-on-surface">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 bg-surface-container-low border-b border-outline-variant">
          <h2 className="text-[13px] font-semibold uppercase tracking-wider">
            Time-Travel Debugger
          </h2>
          <button
            onClick={onClose}
            className="px-3 py-1 text-[11px] bg-surface-container rounded hover:bg-surface-container-high"
          >
            Close
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-1 min-h-0">
          {/* Left: Runs list */}
          <aside className="w-72 border-r border-outline-variant overflow-y-auto shrink-0">
            <div className="px-3 py-2 text-[10px] uppercase tracking-wider text-outline">
              Execution Runs
            </div>
            {isLoading && runs.length === 0 && (
              <div className="px-3 py-8 text-[12px] text-outline text-center">
                Loading...
              </div>
            )}
            {error && (
              <div className="px-3 py-2 text-[11px] text-red-400">{error}</div>
            )}
            {runs.map((run) => (
              <button
                key={run.id}
                onClick={() => handleRunClick(run.id)}
                className={`w-full text-left px-3 py-2 text-[12px] border-b border-surface-container-low hover:bg-surface-container-low ${
                  selectedRunId === run.id ? "bg-surface-container" : ""
                }`}
              >
                <div className="truncate font-medium">{run.query}</div>
                <div className="flex gap-2 mt-1 text-[10px] text-outline">
                  <span>{run.agent_id}</span>
                  <span>•</span>
                  <span>{Math.round(run.duration_ms ?? 0)}ms</span>
                  <span>•</span>
                  <span>{run.success ? "ok" : "incomplete"}</span>
                </div>
              </button>
            ))}
          </aside>

          {/* Center: Steps */}
          <aside className="w-64 border-r border-outline-variant overflow-y-auto shrink-0">
            <div className="px-3 py-2 text-[10px] uppercase tracking-wider text-outline">
              Steps
            </div>
            {steps.map((step) => (
              <button
                key={step.id}
                onClick={() => handleStepClick(step.id)}
                className={`w-full text-left px-3 py-2 text-[11px] border-b border-surface-container-low hover:bg-surface-container-low ${
                  selectedStep?.id === step.id ? "bg-surface-container" : ""
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="w-2 h-2 rounded-full inline-block shrink-0"
                    style={{
                      backgroundColor:
                        NODE_COLORS[step.node_name] ?? "#94a3b8",
                    }}
                  />
                  <span className="text-[10px] opacity-50">
                    #{step.step_number}
                  </span>
                  <span className="font-medium">{step.node_name}</span>
                </div>
                {step.tool_name && (
                  <div className="mt-1 text-[10px] text-[#f59e0b] truncate">
                    → {step.tool_name}
                  </div>
                )}
                {step.needs_confirmation && (
                  <div className="mt-1 text-[10px] text-[#ef4444]">
                    ⚠ confirmation
                  </div>
                )}
              </button>
            ))}
          </aside>

          {/* Right: Detail */}
          <main className="flex-1 overflow-y-auto p-4">
            {selectedStep ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <span
                    className="w-3 h-3 rounded-full inline-block"
                    style={{
                      backgroundColor:
                        NODE_COLORS[selectedStep.node_name] ?? "#94a3b8",
                    }}
                  />
                  <span className="text-[13px] font-semibold">
                    Step #{selectedStep.step_number}: {selectedStep.node_name}
                  </span>
                </div>

                {selectedStep.tool_name && (
                  <div className="bg-surface-container-low rounded p-3">
                    <div className="text-[10px] uppercase text-outline mb-1">
                      Tool Call
                    </div>
                    <div className="text-[12px] font-medium text-[#f59e0b]">
                      {selectedStep.tool_name}
                    </div>
                    {selectedStep.tool_args_json && (
                      <pre className="mt-1 text-[11px] text-on-surface-variant overflow-x-auto whitespace-pre-wrap">
                        {JSON.stringify(
                          JSON.parse(selectedStep.tool_args_json),
                          null,
                          2
                        )}
                      </pre>
                    )}
                  </div>
                )}

                {selectedStep.output_preview && (
                  <div className="bg-surface-container-low rounded p-3">
                    <div className="text-[10px] uppercase text-outline mb-1">
                      Output
                    </div>
                    <pre className="text-[11px] text-on-surface-variant overflow-x-auto whitespace-pre-wrap">
                      {selectedStep.output_preview}
                    </pre>
                  </div>
                )}

                {selectedStep.tool_result_preview && (
                  <div className="bg-surface-container-low rounded p-3">
                    <div className="text-[10px] uppercase text-outline mb-1">
                      Tool Result
                    </div>
                    <pre className="text-[11px] text-[#22c55e] overflow-x-auto whitespace-pre-wrap">
                      {selectedStep.tool_result_preview}
                    </pre>
                  </div>
                )}

                {selectedStep.tokens && selectedStep.tokens.length > 0 && (
                  <div className="bg-surface-container-low rounded p-3">
                    <div className="text-[10px] uppercase text-outline mb-1">
                      Tokens ({selectedStep.tokens.length})
                    </div>
                    <div className="text-[11px] text-on-surface-variant break-all leading-relaxed max-h-32 overflow-y-auto">
                      {selectedStep.tokens
                        .filter((t) => !t.is_final)
                        .map((t) => t.token_text)
                        .join("")}
                    </div>
                  </div>
                )}

                {selectedStep.input_preview && (
                  <div className="bg-surface-container-low rounded p-3">
                    <div className="text-[10px] uppercase text-outline mb-1">
                      Input Preview
                    </div>
                    <pre className="text-[11px] text-on-surface-variant overflow-x-auto whitespace-pre-wrap">
                      {selectedStep.input_preview}
                    </pre>
                  </div>
                )}

                <div className="text-[10px] text-outline">
                  Timestamp:{" "}
                  {new Date(selectedStep.timestamp * 1000).toISOString()}
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-[12px] text-outline">
                {steps.length > 0
                  ? "Select a step to inspect"
                  : "Select a run to view its steps"}
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
