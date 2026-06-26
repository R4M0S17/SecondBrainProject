import { create } from "zustand";
import type { AppConfig, LocalModel, LlamaCppModel, StatusResponse, HealthResponse } from "../api/types";
import { getConfig, updateConfig, startIndex, getModels, getLlamaCppModels } from "../api/client";
import i18n from "../i18n";

const FALLBACK_LLAMA_CPP_MODELS: LlamaCppModel[] = [
  { name: "Qwen3.5-2B-UD-Q4_K_XL.gguf", size_gb: 1.2, provider: "llama_cpp" },
  { name: "qwen2.5-0.5b-instruct-q5_k_m.gguf", size_gb: 0.5, provider: "llama_cpp" },
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
  pendingModel: string | null;

  load: () => Promise<void>;
  loadModels: () => Promise<void>;
  loadLlamaCppModels: () => Promise<void>;
  patch: (partial: Partial<AppConfig>) => Promise<void>;
  checkModelSwitch: (status: StatusResponse | null, health: HealthResponse | null) => void;
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
  profile: "normal",
  low_power_available: false,
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
  pendingModel: null,

  load: async () => {
    try {
      const config = await getConfig();
      const normalized: AppConfig = {
        ...config,
        profile: config.low_power_available ? config.profile ?? "normal" : "normal",
      };
      if (!config.low_power_available) {
        localStorage.setItem("cerebro_selected_profile", "normal");
      }
      set({ config: normalized, isDirty: false, error: null });
      if (config.locale) {
        i18n.changeLanguage(config.locale);
      }
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
    if (!config.low_power_available && partial.profile === "low-power") {
      set({ error: "Low Power mode is in development and not available yet." });
      return;
    }
    const merged = { ...config, ...partial };
    set({ config: merged, isDirty: true, isSaving: true });
    if (partial.model) set({ activeModel: partial.model, switchingModel: true, pendingModel: partial.model });
    try {
      const saved = await updateConfig(partial);
      set({ config: saved, isDirty: false, isSaving: false, error: null });
      // If a model switch was requested, poll engine health until it confirms
      // the switch completed (backend kills + restarts + health-checks before responding,
      // but there may be a brief window where status hasn't caught up).
      if (partial.model) {
        const pending = partial.model;
        for (let i = 0; i < 15; i++) {
          await new Promise((r) => setTimeout(r, 2000));
          try {
            const [statusRes, healthRes] = await Promise.all([
              fetch("http://127.0.0.1:7842/api/status"),
              fetch("http://127.0.0.1:7842/api/health"),
            ]);
            const st = await statusRes.json();
            const hl = await healthRes.json();
            // Use status.model (backend config model), NOT current_model_id
            // (fleet routing model like smollm2-360m-q8)
            const currentModel = st?.model;
            if (currentModel === pending && hl?.llama_server === "up" && st?.engine_ok === true) {
              break;
            }
          } catch {
            // engine still restarting — keep polling
          }
        }
        set({ switchingModel: false, pendingModel: null });
      }
    } catch (e) {
      set({
        isSaving: false,
        switchingModel: false,
        pendingModel: null,
        error: e instanceof Error ? e.message : "Save failed",
      });
    }
  },

  checkModelSwitch: (status, health) => {
    const { pendingModel } = get();
    if (!pendingModel) return;
    // Use status.model (the backend config model), NOT current_model_id
    // (which is the fleet orchestrator's routing model like smollm2-360m-q8)
    const currentModel = status?.model;
    const engineUp = health?.llama_server === "up" && status?.engine_ok === true;
    if (currentModel === pendingModel && engineUp) {
      set({ switchingModel: false, pendingModel: null });
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
