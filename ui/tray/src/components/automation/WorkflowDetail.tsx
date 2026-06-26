import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Workflow, WorkflowRun, WorkflowParameter, WorkflowStep } from "../../api/types";
import { exportWorkflow } from "../../api/client";
import { formatRelativeTime } from "../../utils/time";
import WorkflowScriptPanel from "./WorkflowScriptPanel";
import WorkflowParamForm from "./WorkflowParamForm";
import WorkflowRunConfirm from "./WorkflowRunConfirm";
import WorkflowRunResult from "./WorkflowRunResult";
import WorkflowRunHistory from "./WorkflowRunHistory";

interface WorkflowDetailProps {
  workflow: Workflow;
  runs: WorkflowRun[];
  runResult: string | null;
  lastRunSuccess: boolean | null;
  isRunning: boolean;
  onRun: (id: string, params: Record<string, string>, options?: { dryRun?: boolean }) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, name: string) => void;
  onUpdateSteps: (id: string, steps: WorkflowStep[]) => void;
}

function defaultParamValues(parameters: WorkflowParameter[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const p of parameters) {
    if (p.default != null) out[p.name] = String(p.default);
    else out[p.name] = "";
  }
  return out;
}

export default function WorkflowDetail({
  workflow,
  runs,
  runResult,
  lastRunSuccess,
  isRunning,
  onRun,
  onDelete,
  onRename,
  onUpdateSteps,
}: WorkflowDetailProps) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [editingSteps, setEditingSteps] = useState(false);
  const [nameDraft, setNameDraft] = useState(workflow.name);
  const [stepDrafts, setStepDrafts] = useState<WorkflowStep[]>(workflow.steps);
  const [paramValues, setParamValues] = useState(() => defaultParamValues(workflow.parameters));
  const [showRunConfirm, setShowRunConfirm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [pendingRunId, setPendingRunId] = useState<string | null>(null);

  useEffect(() => {
    setNameDraft(workflow.name);
    setStepDrafts(workflow.steps);
    setParamValues(defaultParamValues(workflow.parameters));
    setEditingSteps(false);
  }, [workflow.id, workflow.name, workflow.parameters, workflow.steps]);

  const commitRename = useCallback(() => {
    const trimmed = nameDraft.trim();
    if (trimmed && trimmed !== workflow.name) {
      onRename(workflow.id, trimmed);
    }
    setEditing(false);
  }, [nameDraft, onRename, workflow.id, workflow.name]);

  const requestRun = useCallback(
    (id: string = workflow.id) => {
      setPendingRunId(id);
      setShowRunConfirm(true);
    },
    [workflow.id],
  );

  const confirmRun = useCallback(() => {
    const id = pendingRunId ?? workflow.id;
    setShowRunConfirm(false);
    setPendingRunId(null);
    onRun(id, paramValues, { dryRun });
    setDryRun(false);
  }, [dryRun, onRun, paramValues, pendingRunId, workflow.id]);

  const handleExport = useCallback(async () => {
    const data = await exportWorkflow(workflow.id);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${workflow.name.replace(/\s+/g, "-").toLowerCase()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [workflow.id, workflow.name]);

  const saveSteps = useCallback(() => {
    onUpdateSteps(workflow.id, stepDrafts);
    setEditingSteps(false);
  }, [onUpdateSteps, stepDrafts, workflow.id]);

  return (
    <div className="space-y-5 px-6 md:px-10 py-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {editing ? (
            <input
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              onBlur={commitRename}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitRename();
                if (e.key === "Escape") {
                  setNameDraft(workflow.name);
                  setEditing(false);
                }
              }}
              autoFocus
              className="text-[18px] font-semibold bg-surface-container-low/60 border border-outline-variant/20 rounded-lg px-2 py-1 w-full max-w-md text-on-surface"
            />
          ) : (
            <h2
              className="text-[18px] font-semibold text-on-surface cursor-text"
              onDoubleClick={() => setEditing(true)}
            >
              {workflow.name}
            </h2>
          )}
          {workflow.description && (
            <p className="text-[13px] text-on-surface-variant/70 mt-1">{workflow.description}</p>
          )}
        </div>
        <div className="flex gap-2 shrink-0 flex-wrap justify-end">
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="px-3 py-1.5 text-[12px] rounded-lg bg-surface-container-low/60 text-on-surface-variant hover:bg-surface-container/60 active:scale-[0.98] transition-all"
            title={t("workflows.rename")}
          >
            <span className="material-symbols-outlined text-[16px] align-middle">edit</span>
          </button>
          <button
            type="button"
            onClick={() => void handleExport()}
            className="px-3 py-1.5 text-[12px] rounded-lg bg-surface-container-low/60 text-on-surface-variant hover:bg-surface-container/60 active:scale-[0.98] transition-all"
            title={t("workflows.export")}
          >
            <span className="material-symbols-outlined text-[16px] align-middle">download</span>
          </button>
          <button
            type="button"
            onClick={() => setShowDeleteConfirm(true)}
            className="px-3 py-1.5 text-[12px] rounded-lg bg-red-900/30 text-red-300 hover:bg-red-800/40 active:scale-[0.98] transition-all"
          >
            {t("workflows.delete")}
          </button>
          <button
            type="button"
            onClick={() => requestRun()}
            disabled={isRunning}
            className="px-3 py-1.5 text-[12px] rounded-lg bg-[#22c55e]/20 text-success-green hover:bg-[#22c55e]/30 active:scale-[0.98] disabled:opacity-50 transition-all flex items-center gap-1.5"
          >
            {isRunning && (
              <span className="w-3 h-3 border-2 border-success-green/30 border-t-success-green rounded-full animate-spin" />
            )}
            {isRunning ? t("workflows.running") : t("workflows.run")}
          </button>
        </div>
      </div>

      <WorkflowParamForm
        parameters={workflow.parameters}
        values={paramValues}
        onChange={(name, value) => setParamValues((prev) => ({ ...prev, [name]: value }))}
      />

      {runResult != null && lastRunSuccess != null && (
        <WorkflowRunResult result={runResult} success={lastRunSuccess} />
      )}

      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-label-caps text-outline tracking-wider uppercase">
            {t("workflows.steps")}
          </h3>
          {workflow.steps.length > 0 && (
            <button
              type="button"
              onClick={() => (editingSteps ? saveSteps() : setEditingSteps(true))}
              className="text-[11px] text-primary-container hover:underline"
            >
              {editingSteps ? t("workflows.save_steps") : t("workflows.edit_steps")}
            </button>
          )}
        </div>
        {workflow.steps.length > 0 ? (
          <ol className="space-y-2">
            {(editingSteps ? stepDrafts : workflow.steps).map((step, idx) => (
              <li
                key={step.order}
                className="flex gap-3 px-4 py-3 rounded-xl bg-surface-container-low/40 border border-outline-variant/10"
              >
                <span className="text-[12px] font-mono text-outline w-6 shrink-0">{step.order}.</span>
                <div className="min-w-0 flex-1">
                  {editingSteps ? (
                    <input
                      value={step.action}
                      onChange={(e) => {
                        const next = [...stepDrafts];
                        next[idx] = { ...step, action: e.target.value };
                        setStepDrafts(next);
                      }}
                      className="w-full text-[13px] bg-surface-container-low/60 border border-outline-variant/20 rounded px-2 py-1 text-on-surface"
                    />
                  ) : (
                    <>
                      {step.app && (
                        <span className="text-[11px] text-primary-container/80 font-medium">{step.app}</span>
                      )}
                      <p className="text-[13px] text-on-surface">{step.action}</p>
                      {step.detail && (
                        <p className="text-[11px] text-outline mt-0.5">{step.detail}</p>
                      )}
                    </>
                  )}
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-[12px] text-outline">{t("workflows.no_steps")}</p>
        )}
      </section>

      <WorkflowRunHistory runs={runs} />

      {workflow.workflow_type === "desktop" && (
        <WorkflowScriptPanel applescript={workflow.applescript} />
      )}

      <div className="flex flex-wrap gap-4 text-[11px] text-outline pt-2">
        <span>{t("workflows.list_runs", { count: workflow.run_count })}</span>
        {workflow.last_run != null && (
          <span>
            {t("workflows.last_run")}: {formatRelativeTime(new Date(workflow.last_run * 1000))}
          </span>
        )}
      </div>

      {showRunConfirm && (
        <WorkflowRunConfirm
          workflow={workflow}
          dryRun={dryRun}
          onDryRunChange={setDryRun}
          onConfirm={confirmRun}
          onCancel={() => {
            setShowRunConfirm(false);
            setPendingRunId(null);
            setDryRun(false);
          }}
        />
      )}

      {showDeleteConfirm && (
        <dialog
          className="fixed inset-0 bg-black/60 backdrop-blur-[4px] z-[70] flex items-center justify-center p-6"
          open
        >
          <div className="w-full max-w-sm bg-surface-container rounded-xl border border-outline-variant p-5 space-y-4">
            <p className="text-[14px] text-on-surface">{t("workflows.delete_confirm", { name: workflow.name })}</p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(false)}
                className="flex-1 h-10 rounded-lg border border-outline-variant text-sm"
              >
                {t("workflows.record_cancel")}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowDeleteConfirm(false);
                  onDelete(workflow.id);
                }}
                className="flex-1 h-10 rounded-lg bg-red-800/50 text-red-200 text-sm font-medium"
              >
                {t("workflows.delete")}
              </button>
            </div>
          </div>
        </dialog>
      )}
    </div>
  );
}
