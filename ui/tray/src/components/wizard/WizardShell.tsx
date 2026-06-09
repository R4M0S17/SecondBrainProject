import { useState } from "react";
import { useWizardStore } from "../../stores/wizard";
import { wizardSetFolders, wizardComplete } from "../../api/client";
import WizardDots from "./WizardDots";
import StepBackend from "./StepBackend";
import StepLlamaCpp from "./StepLlamaCpp";
import StepModel from "./StepModel";
import StepFolders from "./StepFolders";

const LOCAL_LABELS = ["Choose Backend", "Start llama.cpp", "Check Models", "Add Folders"];
const CLAUDE_LABELS = ["Choose Backend", "Add Folders"];

export default function WizardShell() {
  const { currentStep, mode, advance } = useWizardStore();
  const [stepReady, setStepReady] = useState(false);
  const [isAdvancing, setIsAdvancing] = useState(false);
  const [folders, setFolders] = useState<string[]>([]);

  const handleFolderReady = (ready: boolean, selected: string[]) => {
    setStepReady(ready);
    setFolders(selected);
  };

  const handleContinue = async () => {
    if (!stepReady) return;
    setIsAdvancing(true);
    try {
      if (currentStep === 3) {
        await wizardSetFolders(folders);
        await wizardComplete();
      }
      advance();
    } catch {
      // silently advance — backend may not be running in dev
      advance();
    } finally {
      setIsAdvancing(false);
    }
  };

  const isClaudeMode = mode === "claude";
  const total = isClaudeMode ? 2 : 4;
  const visualStep = isClaudeMode && currentStep === 3 ? 1 : currentStep;
  const labels = isClaudeMode ? CLAUDE_LABELS : LOCAL_LABELS;
  const stepLabel = labels[visualStep] ?? "";

  return (
    <div className="w-full h-full flex flex-col bg-background">
      {/* drag strip — mirrors MainLayout */}
      <div
        className="h-7 bg-surface-container-low shrink-0"
        onMouseDown={() =>
          import("@tauri-apps/api/window")
            .then(({ getCurrentWindow }) => getCurrentWindow().startDragging())
            .catch(() => {})
        }
      />
      <div className="flex-1 flex items-center justify-center">
      <div className="w-[440px] bg-surface-container border border-outline-variant rounded-xl p-[40px_36px] flex flex-col items-center">
        {/* Header */}
        <div className="flex flex-col items-center text-center mb-6">
          <svg
            className="w-10 h-10 text-primary mb-3"
            viewBox="0 0 24 24"
            fill="currentColor"
            aria-hidden="true"
          >
            <path d="M12 2C8.13 2 5 5.13 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26C17.81 13.47 19 11.38 19 9c0-3.87-3.13-7-7-7zm0 2c2.76 0 5 2.24 5 5 0 1.85-1.01 3.47-2.5 4.33-.31.18-.5.51-.5.87V16h-4v-1.8c0-.36-.19-.69-.5-.87C8.01 12.47 7 10.85 7 9c0-2.76 2.24-5 5-5zm-1 13h2v1h-2v-1z"/>
          </svg>
          <h1 className="text-[22px] font-bold leading-[28px] tracking-[-0.01em] text-[#e8eaf0] mb-1">
            Cerebro
          </h1>
          <p className="text-[14px] text-outline">Your private AI second brain</p>
        </div>

        {/* Step dots */}
        <WizardDots step={visualStep} total={total} label={stepLabel} />

        {/* Step content */}
        {currentStep === 0 && <StepBackend onReady={setStepReady} />}
        {currentStep === 1 && mode === "local" && <StepLlamaCpp onReady={setStepReady} />}
        {currentStep === 2 && mode === "local" && <StepModel onReady={setStepReady} />}
        {currentStep === 3 && <StepFolders onReady={handleFolderReady} />}

        {/* Continue button */}
        <button
          onClick={handleContinue}
          disabled={!stepReady || isAdvancing}
          className={`w-full py-3 rounded-lg font-bold text-[14px] flex items-center justify-center gap-2 transition-all ${
            stepReady && !isAdvancing
              ? "bg-primary-container text-on-primary-container hover:opacity-90 active:scale-[0.98]"
              : "bg-surface-container text-outline cursor-not-allowed"
          }`}
        >
          {isAdvancing ? "Please wait…" : currentStep === 3 ? "Finish" : "Continue"}
          {!isAdvancing && (
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          )}
        </button>
      </div>
      </div>
    </div>
  );
}
