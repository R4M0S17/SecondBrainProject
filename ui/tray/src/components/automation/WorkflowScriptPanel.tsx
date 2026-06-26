import { useTranslation } from "react-i18next";

interface WorkflowScriptPanelProps {
  applescript: string;
}

export default function WorkflowScriptPanel({ applescript }: WorkflowScriptPanelProps) {
  const { t } = useTranslation();

  if (!applescript) return null;

  return (
    <details className="bg-surface-container-low/40 rounded-xl border border-outline-variant/10">
      <summary className="px-4 py-3 text-[12px] text-outline cursor-pointer select-none">
        {t("workflows.advanced_script")}
      </summary>
      <pre className="px-4 pb-4 text-[11px] font-mono text-code text-on-surface-variant overflow-x-auto whitespace-pre-wrap">
        {applescript}
      </pre>
    </details>
  );
}
