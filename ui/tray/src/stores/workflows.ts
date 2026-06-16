import { create } from "zustand";
import type { Workflow } from "../api/types";
import {
  listWorkflows,
  getWorkflow,
  deleteWorkflow,
  runWorkflow,
} from "../api/client";

interface WorkflowState {
  workflows: Workflow[];
  selectedId: string | null;
  selected: Workflow | null;
  isLoading: boolean;
  runResult: string | null;
  error: string | null;

  loadAll: () => Promise<void>;
  select: (id: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
  execute: (id: string) => Promise<void>;
  clear: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set) => ({
  workflows: [],
  selectedId: null,
  selected: null,
  isLoading: false,
  runResult: null,
  error: null,

  loadAll: async () => {
    set({ isLoading: true, error: null });
    try {
      const workflows = await listWorkflows();
      set({ workflows });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to load workflows" });
    } finally {
      set({ isLoading: false });
    }
  },

  select: async (id) => {
    set({ isLoading: true, selectedId: id, runResult: null });
    try {
      const wf = await getWorkflow(id);
      set({ selected: wf });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to load workflow" });
    } finally {
      set({ isLoading: false });
    }
  },

  remove: async (id) => {
    set({ isLoading: true });
    try {
      await deleteWorkflow(id);
      set((state) => ({
        workflows: state.workflows.filter((w) => w.id !== id),
        selectedId: state.selectedId === id ? null : state.selectedId,
        selected: state.selectedId === id ? null : state.selected,
      }));
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to delete" });
    } finally {
      set({ isLoading: false });
    }
  },

  execute: async (id) => {
    set({ isLoading: true, runResult: null, error: null });
    try {
      const { result } = await runWorkflow(id);
      set({ runResult: result });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to run workflow" });
    } finally {
      set({ isLoading: false });
    }
  },

  clear: () =>
    set({
      workflows: [],
      selectedId: null,
      selected: null,
      runResult: null,
      error: null,
    }),
}));
