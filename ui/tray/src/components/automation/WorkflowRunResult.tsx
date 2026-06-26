import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

interface WorkflowRunResultProps {
  result: string;
  success: boolean;
}

export default function WorkflowRunResult({ result, success }: WorkflowRunResultProps) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [result]);

  return (
    <div
      ref={ref}
      className={`rounded-xl p-4 border ${
        success
          ? "bg-surface-container-low/40 border-success-green/30"
          : "bg-red-950/20 border-red-800/40"
      }`}
    >
      <div
        className={`text-label-caps mb-2 uppercase tracking-wider flex items-center gap-2 ${
          success ? "text-success-green" : "text-red-300"
        }`}
      >
        <span className="material-symbols-outlined text-[16px]">
          {success ? "check_circle" : "error"}
        </span>
        {success ? t("workflows.result_success") : t("workflows.result_error")}
      </div>
      <pre className="text-[12px] text-on-surface-variant whitespace-pre-wrap">{result}</pre>
    </div>
  );
}
