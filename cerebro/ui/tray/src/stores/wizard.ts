import { create } from "zustand";

type WizardMode = "local" | "claude";

interface WizardState {
  currentStep: 0 | 1 | 2 | 3;
  mode: WizardMode | null;
  isComplete: boolean;
  setMode: (m: WizardMode) => void;
  advance: () => void;
  complete: () => void;
  reset: () => void;
}

export const useWizardStore = create<WizardState>((set, get) => ({
  currentStep: 0,
  mode: null,
  isComplete: false,

  setMode: (m) => set({ mode: m }),

  advance: () => {
    const { currentStep, mode } = get();
    if (currentStep === 0) {
      set({ currentStep: mode === "claude" ? 3 : 1 });
      return;
    }
    const next = currentStep + 1;
    if (next > 3) {
      set({ isComplete: true });
    } else {
      set({ currentStep: next as 1 | 2 | 3 });
    }
  },

  complete: () => set({ isComplete: true }),
  reset: () => set({ currentStep: 0, mode: null, isComplete: false }),
}));
