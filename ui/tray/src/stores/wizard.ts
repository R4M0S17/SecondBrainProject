import { create } from "zustand";

type WizardMode = "local" | "claude" | "none";

interface WizardState {
  currentStep: -1 | 0 | 1 | 2 | 3;
  mode: WizardMode | null;
  isComplete: boolean;
  isQuickMode: boolean;
  setMode: (m: WizardMode) => void;
  setQuickMode: (quick: boolean) => void;
  advance: () => void;
  complete: () => void;
  reset: () => void;
}

export const useWizardStore = create<WizardState>((set, get) => ({
  currentStep: -1,
  mode: null,
  isComplete: false,
  isQuickMode: false,

  setMode: (m) => set({ mode: m }),

  setQuickMode: (quick) => set({ isQuickMode: quick }),

  advance: () => {
    const { currentStep, mode, isQuickMode } = get();

    // Welcome step (-1) -> next step
    if (currentStep === -1) {
      if (isQuickMode) {
        // Quick mode: skip directly to folders (step 3)
        set({ currentStep: 3 });
      } else {
        // Advanced mode: show backend selection (step 0)
        set({ currentStep: 0 });
      }
      return;
    }

    // Backend step (0) -> next based on mode
    if (currentStep === 0) {
      set({ currentStep: mode === "local" ? 1 : 3 });
      return;
    }

    // Folders step (3) -> complete
    if (currentStep === 3) {
      set({ isComplete: true });
      return;
    }

    // Other steps (1, 2) -> advance normally
    const next = currentStep + 1;
    if (next > 3) {
      set({ isComplete: true });
    } else {
      set({ currentStep: next as 1 | 2 | 3 });
    }
  },

  complete: () => set({ isComplete: true }),
  reset: () => set({ currentStep: -1, mode: null, isComplete: false, isQuickMode: false }),
}));
