import { useEffect, useCallback } from "react";
import { useWorkflowStore } from "../../stores/workflows";

export default function WorkflowPanel({ onClose }: { onClose: () => void }) {
  const {
    workflows,
    selected,
    isLoading,
    runResult,
    error,
    loadAll,
    select,
    remove,
    execute,
  } = useWorkflowStore();

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleRun = useCallback(
    (id: string) => {
      execute(id);
    },
    [execute]
  );

  return (
    <div className="fixed inset-0 z-50 flex bg-black/60 backdrop-blur-sm">
      <div className="flex flex-col w-full h-full bg-background text-on-surface">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 bg-surface-container-low border-b border-outline-variant">
          <h2 className="text-[13px] font-semibold uppercase tracking-wider">
            Workflows
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
          {/* Left: Workflow list */}
          <aside className="w-72 border-r border-outline-variant overflow-y-auto shrink-0">
            <div className="px-3 py-2 text-[10px] uppercase tracking-wider text-outline">
              Recorded Workflows
            </div>
            {isLoading && workflows.length === 0 && (
              <div className="px-3 py-8 text-[12px] text-outline text-center">
                Loading...
              </div>
            )}
            {error && (
              <div className="px-3 py-2 text-[11px] text-red-400">{error}</div>
            )}
            {workflows.length === 0 && !isLoading && (
              <div className="px-3 py-8 text-[12px] text-outline text-center">
                No workflows yet. Ask the agent to "start recording" to create
                one.
              </div>
            )}
            {workflows.map((wf) => (
              <button
                key={wf.id}
                onClick={() => select(wf.id)}
                className={`w-full text-left px-3 py-2 text-[12px] border-b border-surface-container-low hover:bg-surface-container-low ${
                  selected?.id === wf.id ? "bg-surface-container" : ""
                }`}
              >
                <div className="truncate font-medium">{wf.name}</div>
                <div className="flex gap-2 mt-1 text-[10px] text-outline">
                  <span>{wf.run_count} runs</span>
                  {wf.tags.length > 0 && <span>• {wf.tags.join(", ")}</span>}
                </div>
              </button>
            ))}
          </aside>

          {/* Right: Detail */}
          <main className="flex-1 overflow-y-auto p-4">
            {selected ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-[15px] font-semibold">
                      {selected.name}
                    </h3>
                    <p className="text-[12px] text-outline mt-1">
                      {selected.description}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => remove(selected.id)}
                      className="px-3 py-1 text-[11px] bg-red-800/40 text-red-300 rounded hover:bg-red-700/50"
                    >
                      Delete
                    </button>
                    <button
                      onClick={() => handleRun(selected.id)}
                      className="px-3 py-1 text-[11px] bg-[#22c55e]/20 text-[#22c55e] rounded hover:bg-[#22c55e]/30"
                      disabled={isLoading}
                    >
                      {isLoading ? "Running..." : "Run"}
                    </button>
                  </div>
                </div>

                {runResult && (
                  <div className="bg-surface-container-low rounded p-3 border border-[#22c55e]/30">
                    <div className="text-[10px] uppercase text-[#22c55e] mb-1">
                      Result
                    </div>
                    <pre className="text-[12px] text-on-surface-variant whitespace-pre-wrap">
                      {runResult}
                    </pre>
                  </div>
                )}

                {selected.parameters.length > 0 && (
                  <div className="bg-surface-container-low rounded p-3">
                    <div className="text-[10px] uppercase text-outline mb-1">
                      Parameters
                    </div>
                    {selected.parameters.map((p, i) => (
                      <div key={i} className="text-[12px] text-on-surface-variant mt-1">
                        <span className="text-[#f59e0b]">{p.name}</span>
                        {" ("}
                        {p.type}
                        {") "}
                        — {p.description}
                      </div>
                    ))}
                  </div>
                )}

                <div className="bg-surface-container-low rounded p-3">
                  <div className="text-[10px] uppercase text-outline mb-1">
                    AppleScript
                  </div>
                  <pre className="text-[11px] text-on-surface-variant overflow-x-auto whitespace-pre-wrap font-mono">
                    {selected.applescript}
                  </pre>
                </div>

                <div className="flex gap-4 text-[10px] text-outline">
                  <span>Created: {new Date(selected.created_at * 1000).toLocaleString()}</span>
                  <span>Run count: {selected.run_count}</span>
                  {selected.last_run && (
                    <span>
                      Last run: {new Date(selected.last_run * 1000).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-[12px] text-outline">
                {workflows.length > 0
                  ? "Select a workflow to inspect"
                  : "No workflows yet"}
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
