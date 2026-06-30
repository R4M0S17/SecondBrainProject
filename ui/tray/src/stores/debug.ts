import { create } from "zustand";
import type { DebugRun, DebugStep, DebugStepDetail } from "../api/types";
import {
  listDebugRuns,
  getDebugRunSteps,
  getDebugStepDetail,
} from "../api/client";

interface DebugState {
  runs: DebugRun[];
  selectedRunId: string | null;
  steps: DebugStep[];
  selectedStep: DebugStepDetail | null;
  isLoading: boolean;
  error: string | null;
  debugPanelOpen: boolean;

  loadRuns: () => Promise<void>;
  selectRun: (id: string) => Promise<void>;
  selectStep: (stepId: string) => Promise<void>;
  clear: () => void;
  setDebugPanelOpen: (v: boolean) => void;
}

export const useDebugStore = create<DebugState>((set) => ({
  runs: [],
  selectedRunId: null,
  steps: [],
  selectedStep: null,
  isLoading: false,
  error: null,
  debugPanelOpen: false,

  loadRuns: async () => {
    set({ isLoading: true, error: null });
    try {
      const runs = await listDebugRuns();
      set({ runs });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to load runs" });
    } finally {
      set({ isLoading: false });
    }
  },

  selectRun: async (id) => {
    set({ isLoading: true, selectedRunId: id, steps: [], selectedStep: null });
    try {
      const steps = await getDebugRunSteps(id);
      set({ steps });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to load steps" });
    } finally {
      set({ isLoading: false });
    }
  },

  selectStep: async (stepId) => {
    set({ isLoading: true });
    try {
      const detail = await getDebugStepDetail(stepId);
      set({ selectedStep: detail });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to load step" });
    } finally {
      set({ isLoading: false });
    }
  },

  clear: () =>
    set({
      runs: [],
      selectedRunId: null,
      steps: [],
      selectedStep: null,
      error: null,
    }),

  setDebugPanelOpen: (v) => set({ debugPanelOpen: v }),
}));
