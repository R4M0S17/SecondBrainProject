import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getLlamaCppModels, wizardCheckModels } from "../../api/client";
import type { LlamaCppModel } from "../../api/types";

interface StepModelProps {
  onReady: (ready: boolean) => void;
}

type CheckState = "checking" | "ok" | "missing" | "error";

export default function StepModel({ onReady }: StepModelProps) {
  const { t } = useTranslation();
  const [state, setState] = useState<CheckState>("checking");
  const [message, setMessage] = useState<string>("");
  const [models, setModels] = useState<LlamaCppModel[]>([]);

  const check = useCallback(async () => {
    setState("checking");
    onReady(false);
    try {
      const [modelRes, llamaModels] = await Promise.all([
        wizardCheckModels(),
        getLlamaCppModels(),
      ]);
      const { models: found } = llamaModels;

      if (modelRes.status === "skipped") {
        setMessage(modelRes.message ?? "");
        setModels([]);
        if (modelRes.ok) {
          setState("ok");
          onReady(true);
        } else {
          setState("missing");
          onReady(false);
        }
        return;
      }

      setMessage(modelRes.message ?? modelRes.detail ?? "");
      setModels(found);
      if (modelRes.ok) {
        setState("ok");
        onReady(true);
      } else {
        setState("missing");
      }
    } catch (e) {
      setState("error");
      setMessage((e as Error).message ?? "Check failed");
    }
  }, [onReady]);

  useEffect(() => {
    check();
  }, [check]);

  return (
    <div className="w-full space-y-3 mb-6">
      <p className="text-[14px] text-[#e8eaf0] text-center mb-4">
        {t("wizard.verify_models")}{" "}
        <code className="text-primary-container bg-surface-container px-1 rounded">bin/models/</code>.
      </p>

      {/* Status block */}
      <div
        className={`rounded-lg border p-[14px_16px] transition-colors ${
          state === "ok"
            ? "border-success-green/40 bg-success-green/5"
            : state === "missing" || state === "error"
            ? "border-error/40 bg-error/5"
            : "border-outline-variant/50 bg-background"
        }`}
      >
        <div className="flex items-center gap-3">
          {state === "checking" ? (
            <div className="w-2 h-2 rounded-full border-2 border-outline border-t-transparent animate-spin shrink-0" />
          ) : state === "ok" ? (
            <div className="w-2 h-2 rounded-full bg-success-green shrink-0" />
          ) : (
            <div className="w-2 h-2 rounded-full bg-error shrink-0" />
          )}
          <span
            className={`text-[14px] font-medium ${
              state === "checking"
                ? "text-outline"
                : state === "ok"
                ? "text-success-green"
                : "text-error"
            }`}
          >
            {state === "checking"
              ? t("wizard.scanning")
              : state === "ok"
              ? t("wizard.models_found", { count: models.length })
              : message || t("wizard.no_models")}
          </span>
        </div>

        {state === "ok" && models.length > 0 && (
          <ul className="mt-3 space-y-1">
            {models.map((m) => (
              <li key={m.name} className="flex items-center justify-between text-[12px]">
                <span className="font-mono text-[#e8eaf0]">{m.name}</span>
                <span className="text-outline">{m.size_gb.toFixed(1)} GB</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {(state === "missing" || state === "error") && (
        <>
          <p className="text-[12px] text-outline text-center">
            {t("wizard.retry_models")}{" "}
            <code className="text-primary-container bg-surface-container px-1 rounded">bin/models/</code>
            {t("wizard.then_click")}
          </p>
          <div className="flex justify-center">
            <button
              onClick={check}
              className="px-4 py-1.5 text-[12px] bg-primary-container text-on-primary-container rounded hover:opacity-90 transition-opacity font-semibold"
            >
              {t("wizard.retry")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
