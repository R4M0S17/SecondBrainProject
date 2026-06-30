import { create } from "zustand";
import type { RecordingStatus, Workflow, WorkflowRecipe, WorkflowRun } from "../api/types";
import { ApiError } from "../api/errors";
import {
  listWorkflows,
  getWorkflow,
  deleteWorkflow,
  runWorkflow,
  listWorkflowRuns,
  startWorkflowRecording,
  getWorkflowRecordingStatus,
  stopWorkflowRecording,
  cancelWorkflowRecording,
  updateWorkflow as apiUpdateWorkflow,
  listRecipeTemplates,
  installRecipe,
  importWorkflow,
} from "../api/client";

export type WorkflowViewTab = "routines" | "recipes" | "templates";
type CreateMode = "list" | "record" | "templates" | null;

interface WorkflowState {
  workflows: Workflow[];
  selectedId: string | null;
  selected: Workflow | null;
  isLoading: boolean;
  isRunning: boolean;
  runResult: string | null;
  lastRunSuccess: boolean | null;
  runs: WorkflowRun[];
  templates: WorkflowRecipe[];
  templatesLoaded: boolean;
  error: string | null;
  searchQuery: string;
  viewTab: WorkflowViewTab;
  recordingStatus: RecordingStatus | null;
  isRecording: boolean;
  isGeneralizing: boolean;
  openCreateMode: CreateMode;

  setSearchQuery: (query: string) => void;
  setViewTab: (tab: WorkflowViewTab) => void;
  setOpenCreateMode: (mode: CreateMode) => void;
  loadAll: () => Promise<void>;
  loadTemplates: () => Promise<void>;
  loadRuns: (id: string) => Promise<void>;
  select: (id: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
  execute: (id: string, params?: Record<string, string>, options?: { dryRun?: boolean }) => Promise<void>;
  installTemplate: (templateId: string, name?: string) => Promise<Workflow | null>;
  importFromFile: (file: File) => Promise<Workflow | null>;
  updateWorkflow: (
    id: string,
    patch: {
      name?: string;
      description?: string;
      tags?: string[];
      steps?: import("../api/types").WorkflowStep[];
      applescript?: string;
    },
  ) => Promise<void>;
  startRecording: () => Promise<void>;
  pollRecordingStatus: () => Promise<void>;
  stopRecording: (name?: string) => Promise<Workflow | null>;
  cancelRecording: () => Promise<void>;
  clear: () => void;
}

// ─── Recording overlay helpers ────────────────────────────────────────────────

let _overlayUnlisten: (() => void) | null = null;

async function _showRecordingOverlay(get: () => WorkflowState) {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const { listen } = await import("@tauri-apps/api/event");
    await invoke("show_recording_overlay");
    _overlayUnlisten?.();
    const unStop = await listen<void>("recording-overlay:stop", () => {
      void get().stopRecording();
    });
    const unCancel = await listen<void>("recording-overlay:cancel", () => {
      void get().cancelRecording();
    });
    _overlayUnlisten = () => { unStop(); unCancel(); };
  } catch {
    // dev browser fallback — the in-app overlay (MainLayout) handles it
  }
}

async function _hideRecordingOverlay() {
  _overlayUnlisten?.();
  _overlayUnlisten = null;
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("hide_recording_overlay");
  } catch { /* not in Tauri */ }
}

async function _focusMainWindow() {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("focus_main_window");
  } catch { /* not in Tauri */ }
}

// ─────────────────────────────────────────────────────────────────────────────

function resolveWorkflowError(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 404 && e.detail === "Not Found") {
      return "workflows.error.backend_outdated";
    }
    return e.detail || "workflows.error.generic";
  }
  const msg = e instanceof Error ? e.message : String(e);
  if (msg.includes("Request failed") || msg.includes("ECONNREFUSED")) {
    return "workflows.error.backend_offline";
  }
  return msg || "workflows.error.generic";
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  workflows: [],
  selectedId: null,
  selected: null,
  isLoading: false,
  isRunning: false,
  runResult: null,
  lastRunSuccess: null,
  runs: [],
  templates: [],
  templatesLoaded: false,
  error: null,
  searchQuery: "",
  viewTab: "routines",
  recordingStatus: null,
  isRecording: false,
  isGeneralizing: false,
  openCreateMode: null,

  setSearchQuery: (query) => set({ searchQuery: query }),

  setViewTab: (tab) => set({ viewTab: tab }),

  setOpenCreateMode: (mode) => set({ openCreateMode: mode }),

  loadAll: async () => {
    set({ isLoading: true, error: null });
    try {
      const workflows = await listWorkflows();
      set({ workflows });
    } catch (e) {
      set({ error: resolveWorkflowError(e) });
    } finally {
      set({ isLoading: false });
    }
  },

  loadTemplates: async () => {
    set({ templatesLoaded: false });
    try {
      const templates = await listRecipeTemplates();
      set({ templates, templatesLoaded: true });
    } catch (e) {
      set({ templatesLoaded: true, error: resolveWorkflowError(e) });
    }
  },

  loadRuns: async (id) => {
    try {
      const runs = await listWorkflowRuns(id);
      set({ runs });
    } catch {
      set({ runs: [] });
    }
  },

  select: async (id) => {
    set({ isLoading: true, selectedId: id, runResult: null, lastRunSuccess: null });
    try {
      const wf = await getWorkflow(id);
      set({ selected: wf });
      await get().loadRuns(id);
    } catch (e) {
      set({ error: resolveWorkflowError(e) });
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
        runs: state.selectedId === id ? [] : state.runs,
      }));
    } catch (e) {
      set({ error: resolveWorkflowError(e) });
    } finally {
      set({ isLoading: false });
    }
  },

  execute: async (id, params, options) => {
    set({ isRunning: true, runResult: null, lastRunSuccess: null, error: null });
    try {
      const response = await runWorkflow(id, params, { dryRun: options?.dryRun });
      set({
        runResult: response.result,
        lastRunSuccess: response.success,
      });
      if (response.success) {
        window.dispatchEvent(new CustomEvent("cerebro-notification", { detail: { tab: "workflows" } }));
      }
      await get().loadAll();
      await get().loadRuns(id);
      if (get().selectedId === id) {
        const wf = await getWorkflow(id);
        set({ selected: wf });
      }
    } catch (e) {
      set({ error: resolveWorkflowError(e), lastRunSuccess: false });
    } finally {
      set({ isRunning: false });
    }
  },

  installTemplate: async (templateId, name) => {
    set({ isLoading: true, error: null });
    try {
      const wf = await installRecipe(templateId, name);
      await get().loadAll();
      await get().select(wf.id);
      set({ viewTab: "recipes" });
      return wf;
    } catch (e) {
      set({ error: resolveWorkflowError(e) });
      return null;
    } finally {
      set({ isLoading: false });
    }
  },

  importFromFile: async (file) => {
    set({ isLoading: true, error: null });
    try {
      const text = await file.text();
      const parsed = JSON.parse(text) as import("../api/types").WorkflowExport;
      const wf = await importWorkflow(parsed);
      await get().loadAll();
      await get().select(wf.id);
      set({ viewTab: wf.workflow_type === "recipe" ? "recipes" : "routines" });
      return wf;
    } catch {
      set({ error: "workflows.import_error" });
      return null;
    } finally {
      set({ isLoading: false });
    }
  },

  updateWorkflow: async (id, patch) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await apiUpdateWorkflow(id, patch);
      set((state) => ({
        workflows: state.workflows.map((w) => (w.id === id ? updated : w)),
        selected: state.selectedId === id ? updated : state.selected,
      }));
    } catch (e) {
      set({ error: resolveWorkflowError(e) });
    } finally {
      set({ isLoading: false });
    }
  },

  startRecording: async () => {
    set({ error: null });
    try {
      await startWorkflowRecording();
      const status = await getWorkflowRecordingStatus();
      set({ isRecording: true, recordingStatus: status, viewTab: "routines" });
      void _showRecordingOverlay(get);
    } catch (e) {
      set({ error: resolveWorkflowError(e), isRecording: false });
      throw e;
    }
  },

  pollRecordingStatus: async () => {
    try {
      const status = await getWorkflowRecordingStatus();
      set({
        recordingStatus: status,
        isRecording: status.recording,
      });
    } catch {
      // non-fatal
    }
  },

  stopRecording: async (name) => {
    await _hideRecordingOverlay();
    await _focusMainWindow();
    set({ isGeneralizing: true, error: null });
    try {
      const wf = await stopWorkflowRecording(name);
      set({ isRecording: false, recordingStatus: null, isGeneralizing: false });
      await get().loadAll();
      await get().select(wf.id);
      return wf;
    } catch (e) {
      set({
        error: resolveWorkflowError(e),
        isGeneralizing: false,
        isRecording: false,
      });
      return null;
    }
  },

  cancelRecording: async () => {
    await _hideRecordingOverlay();
    try {
      await cancelWorkflowRecording();
    } finally {
      set({ isRecording: false, recordingStatus: null, isGeneralizing: false });
    }
  },

  clear: () =>
    set({
      workflows: [],
      selectedId: null,
      selected: null,
      isLoading: false,
      isRunning: false,
      runResult: null,
      lastRunSuccess: null,
      runs: [],
      templates: [],
      templatesLoaded: false,
      error: null,
      searchQuery: "",
      viewTab: "routines",
      recordingStatus: null,
      isRecording: false,
      isGeneralizing: false,
      openCreateMode: null,
    }),
}));
