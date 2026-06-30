import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getWizardStatus, startEngine, updateConfig, wizardCheckLlamaCpp } from "../../api/client";

interface StepLlamaCppProps {
  onReady: (ready: boolean) => void;
}

export default function StepLlamaCpp({ onReady }: StepLlamaCppProps) {
  const { t } = useTranslation();
  const [running, setRunning] = useState<boolean | null>(null);
  const [skippedReason, setSkippedReason] = useState<string | null>(null);
  const [recommendLite, setRecommendLite] = useState(false);
  const [liteSaving, setLiteSaving] = useState(false);
  const [liteApplied, setLiteApplied] = useState(false);
  const [liteError, setLiteError] = useState<string | null>(null);
  const [engineStarting, setEngineStarting] = useState(false);
  const [engineError, setEngineError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getWizardStatus()
      .then((s) => {
        if (!cancelled && s.recommend_lite) setRecommendLite(true);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const res = await wizardCheckLlamaCpp();
        if (!cancelled) {
          if (res.status === "skipped") {
            setRunning(true);
            setSkippedReason(res.reason ?? null);
            onReady(true);
          } else {
            setSkippedReason(null);
            setRunning(res.running);
            onReady(res.running);
          }
        }
      } catch {
        if (!cancelled) {
          setRunning(false);
          onReady(false);
        }
      }
    }

    check();
    const id = setInterval(check, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [onReady]);

  async function applyLiteProfile() {
    setLiteSaving(true);
    setLiteError(null);
    try {
      await updateConfig({
        inference_backend: "llamacpp",
        model: "Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        mlx_enabled: false,
      });
      setLiteApplied(true);
    } catch (e: unknown) {
      setLiteError(e instanceof Error ? e.message : "Could not save profile");
    } finally {
      setLiteSaving(false);
    }
  }

  return (
    <div className="w-full space-y-4 mb-6">
      <p className="text-[14px] leading-[20px] text-[#e8eaf0] text-center leading-relaxed">
        {skippedReason
          ? skippedReason
          : t("wizard.llama_desc")}
      </p>

      {recommendLite && !skippedReason && (
        <div className="bg-[#1c2333] border border-[#3d4f7c]/60 rounded-lg p-4 space-y-3">
          <p className="text-[13px] text-[#c4d4f5] text-center leading-relaxed">
            {t("wizard.lite_card")}
          </p>
          <button
            type="button"
            onClick={applyLiteProfile}
            disabled={liteSaving || liteApplied}
            className={`w-full py-2.5 rounded-lg font-semibold text-[13px] transition-all ${
              liteApplied
                ? "bg-surface-container text-outline cursor-default"
                : liteSaving
                  ? "bg-surface-container text-outline cursor-wait"
                  : "bg-[#6366f1] text-white hover:opacity-90 active:scale-[0.99]"
            }`}
          >
            {liteApplied ? t("wizard.lite_saved") : liteSaving ? t("wizard.lite_saving") : t("wizard.lite_button")}
          </button>
          {liteError && (
            <p className="text-[12px] text-error text-center">{liteError}</p>
          )}
          {liteApplied && (
            <p className="text-[11px] text-outline text-center">
              {t("wizard.lite_instructions")}
            </p>
          )}
        </div>
      )}

      {/* Status block */}
      <div className="bg-background rounded-lg p-[14px_16px] flex items-center justify-between border border-outline-variant/50">
        <div className="flex items-center gap-3">
          {running === null ? (
            <div className="w-2 h-2 rounded-full border-2 border-outline border-t-transparent animate-spin" />
          ) : skippedReason ? (
            <div className="w-2 h-2 rounded-full bg-secondary" />
          ) : running ? (
            <div className="w-2 h-2 rounded-full bg-success-green status-dot-pulse" />
          ) : (
            <div className="w-2 h-2 rounded-full bg-error" />
          )}
          <span
            className={`text-[14px] font-medium ${
              running === null
                ? "text-outline"
                : skippedReason
                  ? "text-secondary"
                  : running
                    ? "text-success-green"
                    : "text-error"
            }`}
          >
            {running === null
              ? t("wizard.checking_llama")
              : skippedReason
                ? skippedReason
                : running
                  ? t("wizard.llama_running")
                  : t("wizard.llama_not_detected")}
          </span>
        </div>
        {running !== null && (
          <div
            className={`font-bold text-[10px] px-2 py-1 rounded uppercase tracking-wider ${
              skippedReason
                ? "bg-secondary/15 text-secondary"
                : running
                  ? "bg-success-green/15 text-success-green"
                  : "bg-error/15 text-error"
            }`}
          >
            {skippedReason ? t("wizard.skipped") : running ? t("wizard.detected") : t("wizard.not_found")}
          </div>
        )}
      </div>

      {!skippedReason && !running && running !== null && (
        <div className="space-y-3">
          <button
            type="button"
            onClick={async () => {
              setEngineStarting(true);
              setEngineError(null);
              try {
                await startEngine();
              } catch (e: unknown) {
                setEngineError(e instanceof Error ? e.message : "Failed to start engine");
              } finally {
                setEngineStarting(false);
              }
            }}
            disabled={engineStarting}
            className={`w-full py-2.5 rounded-lg font-semibold text-[13px] transition-all ${
              engineStarting
                ? "bg-surface-container text-outline cursor-wait"
                : "bg-[#6366f1] text-white hover:opacity-90 active:scale-[0.99]"
            }`}
          >
            {engineStarting ? t("wizard.engine_starting") : t("wizard.start_engine")}
          </button>
          {engineError && (
            <p className="text-[12px] text-error text-center">{engineError}</p>
          )}
          <p className="text-[12px] text-outline text-center">
            {t("wizard.llama_instructions")}
          </p>
          <button
            type="button"
            onClick={() => onReady(true)}
            className="w-full text-[12px] text-outline hover:text-[#e8eaf0] underline transition-colors"
          >
            {t("wizard.skip_engine")}
          </button>
        </div>
      )}
    </div>
  );
}
