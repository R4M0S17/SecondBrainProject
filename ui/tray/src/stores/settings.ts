import { create } from "zustand";
import type { AppConfig, LocalModel, LlamaCppModel } from "../api/types";
import { getConfig, updateConfig, startIndex, getModels, getLlamaCppModels } from "../api/client";

const FALLBACK_LLAMA_CPP_MODELS: LlamaCppModel[] = [
  { name: "Qwen3.5-2B-UD-Q4_K_XL.gguf", size_gb: 1.2, provider: "llama_cpp" },
  { name: "Qwen_Qwen3.5-0.8B-Q4_K_M.gguf", size_gb: 0.5, provider: "llama_cpp" },
  { name: "Qwen_Qwen3.5-0.8B-Q5_K_M.gguf", size_gb: 0.6, provider: "llama_cpp" },
  { name: "Qwen_Qwen3.5-2B-Q4_K_M.gguf", size_gb: 1.3, provider: "llama_cpp" },
  { name: "Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf", size_gb: 0.9, provider: "llama_cpp" },
  { name: "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf", size_gb: 0.9, provider: "llama_cpp" },
  { name: "llama-3.2-3b-instruct-q4_k_m.gguf", size_gb: 1.9, provider: "llama_cpp" },
];

interface SettingsState {
  config: AppConfig | null;
  isDirty: boolean;
  isOpen: boolean;
  error: string | null;
  isSaving: boolean;
  activeJobId: string | null;
  models: LocalModel[];
  activeModel: string | null;
  modelsLoading: boolean;
  llamaCppModels: LlamaCppModel[];
  llamaCppLoading: boolean;
  switchingModel: boolean;

  load: () => Promise<void>;
  loadModels: () => Promise<void>;
  loadLlamaCppModels: () => Promise<void>;
  patch: (partial: Partial<AppConfig>) => Promise<void>;
  open: () => void;
  close: () => void;
  startIndexing: (paths: string[]) => Promise<void>;
  clearIndexJob: () => void;
}

const DEFAULT_MODEL = "Qwen3.5-2B-UD-Q4_K_XL.gguf";

const DEFAULT_CONFIG: AppConfig = {
  model: DEFAULT_MODEL,
  watched_folders: [],
  tool_permissions: {
    execute_python: true,
    write_file: true,
    read_file: true,
    search_web: false,
  },
  dnd_enabled: false,
  focus_mode: false,
  embedding_model: "nomic-embed-text",
  inference_backend: "llamacpp",
};

export const useSettingsStore = create<SettingsState>((set, get) => ({
  config: null,
  isDirty: false,
  isOpen: false,
  error: null,
  isSaving: false,
  activeJobId: null,
  models: [],
  activeModel: DEFAULT_MODEL,
  modelsLoading: false,
  llamaCppModels: FALLBACK_LLAMA_CPP_MODELS,
  llamaCppLoading: false,
  switchingModel: false,

  load: async () => {
    try {
      const config = await getConfig();
      set({ config, isDirty: false, error: null });
    } catch {
      // Backend may not be running yet — use defaults silently
      set({ config: DEFAULT_CONFIG, error: null });
    }
    void get().loadModels();
    void get().loadLlamaCppModels();
  },

  loadModels: async () => {
    const { modelsLoading } = get();
    if (modelsLoading) return;
    set({ modelsLoading: true });
    try {
      const r = await getModels();
      set({ models: r.models, activeModel: r.active_model ?? get().activeModel, modelsLoading: false });
    } catch {
      set({ modelsLoading: false });
    }
  },

  loadLlamaCppModels: async () => {
    const { llamaCppLoading } = get();
    if (llamaCppLoading) return;
    set({ llamaCppLoading: true });
    try {
      const r = await getLlamaCppModels();
      const models = r.models.length > 0 ? r.models : FALLBACK_LLAMA_CPP_MODELS;
      set({
        llamaCppModels: models,
        activeModel: r.active_model ?? get().activeModel,
        llamaCppLoading: false,
      });
    } catch {
      // Backend endpoint not yet implemented — keep fallback models
      set({ llamaCppLoading: false });
    }
  },

  patch: async (partial) => {
    const { config } = get();
    if (!config) return;
    const merged = { ...config, ...partial };
    set({ config: merged, isDirty: true, isSaving: true });
    if (partial.model) set({ activeModel: partial.model, switchingModel: true });
    try {
      const saved = await updateConfig(partial);
      set({ config: saved, isDirty: false, isSaving: false, error: null, switchingModel: false });
    } catch (e) {
      set({
        isSaving: false,
        switchingModel: false,
        error: e instanceof Error ? e.message : "Save failed",
      });
    }
  },

  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),

  startIndexing: async (paths) => {
    if (paths.length === 0) return;
    try {
      const res = await startIndex(paths);
      set({ activeJobId: res.job_id });
    } catch {
      // ignore — backend may not be ready
    }
  },

  clearIndexJob: () => set({ activeJobId: null }),
}));
