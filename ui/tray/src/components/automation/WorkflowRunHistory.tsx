import { useTranslation } from "react-i18next";
import type { WorkflowRun } from "../../api/types";
import { formatRelativeTime } from "../../utils/time";

interface WorkflowRunHistoryProps {
  runs: WorkflowRun[];
}

function formatDuration(started: number, finished: number | null): string {
  if (finished == null) return "—";
  const sec = Math.max(0, Math.round(finished - started));
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m ${sec % 60}s`;
}

export default function WorkflowRunHistory({ runs }: WorkflowRunHistoryProps) {
  const { t } = useTranslation();

  if (runs.length === 0) return null;

  return (
    <details className="bg-surface-container-low/30 rounded-xl border border-outline-variant/10">
      <summary className="px-4 py-3 text-label-caps text-outline tracking-wider uppercase cursor-pointer select-none">
        {t("workflows.run_history")} ({runs.length})
      </summary>
      <ul className="divide-y divide-outline-variant/10 max-h-48 overflow-y-auto scrollbar-auto">
        {runs.map((run) => (
          <li key={run.id} className="px-4 py-2.5 flex items-center gap-3 text-[12px]">
            <span
              className={`material-symbols-outlined text-[16px] shrink-0 ${
                run.success ? "text-success-green" : "text-red-400"
              }`}
            >
              {run.success ? "check_circle" : "cancel"}
            </span>
            <span className="text-outline shrink-0 font-mono">
              {formatDuration(run.started_at, run.finished_at)}
            </span>
            <span className="text-on-surface-variant truncate flex-1">
              {run.success ? run.output?.slice(0, 80) : run.error?.slice(0, 80)}
            </span>
            <span className="text-[11px] text-outline shrink-0">
              {formatRelativeTime(new Date(run.started_at * 1000))}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}
