import { create } from "zustand";
import { invoke } from "@tauri-apps/api/core";
import { isTauriRuntime } from "../lib/tauri";
import {
  getEngineStatus,
  getHealth,
  startEngine,
  stopEngine,
} from "../api/client";
import { useSystemStore } from "./system";

interface ServicesState {
  starting: boolean;
  stopping: boolean;
  /** FastAPI :7842 responds to /api/health */
  backendReady: boolean;
  /** User intent from /api/engine/status (desired=on) */
  engineDesired: boolean;
  error: string | null;
  probeBackend: () => Promise<void>;
  syncEngineState: () => Promise<void>;
  turnOn: () => Promise<void>;
  turnOff: () => Promise<void>;
  clearError: () => void;
}

const HEALTH_POLL_MS = 2000;
const HEALTH_POLL_MAX = 150;
const ENGINE_POLL_MS = 2000;
const ENGINE_POLL_MAX = 100;

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : String(error));
}

async function waitForBackend(getLauncherError?: () => Error | null): Promise<void> {
  for (let i = 0; i < HEALTH_POLL_MAX; i++) {
    const launcherError = getLauncherError?.();
    if (launcherError) {
      throw launcherError;
    }
    try {
      await getHealth();
      return;
    } catch {
      await new Promise((r) => setTimeout(r, HEALTH_POLL_MS));
    }
  }
  const launcherError = getLauncherError?.();
  if (launcherError) {
    throw launcherError;
  }
  throw new Error(
    "Backend did not respond in time.\n" +
      "Check ~/.cerebro/logs/backend.log for Python errors.\n" +
      "Restart the app or run: make desktop-backend",
  );
}

async function waitForEngineRunning(): Promise<void> {
  for (let i = 0; i < ENGINE_POLL_MAX; i++) {
    try {
      const status = await getEngineStatus();
      if (status.running) {
        return;
      }
    } catch {
      // backend may still be starting
    }
    await new Promise((r) => setTimeout(r, ENGINE_POLL_MS));
  }
  throw new Error(
    "Engine did not become healthy in time.\n" +
      "Check ~/.cerebro/logs/engine.log for llama-server errors.",
  );
}

export const useServicesStore = create<ServicesState>((set, get) => ({
  starting: false,
  stopping: false,
  backendReady: false,
  engineDesired: false,
  error: null,

  clearError: () => set({ error: null }),

  syncEngineState: async () => {
    try {
      const engineStatus = await getEngineStatus();
      set({ engineDesired: engineStatus.desired === "on", backendReady: true });
      await useSystemStore.getState().refresh();
    } catch {
      set({ backendReady: false, engineDesired: false });
    }
  },

  probeBackend: async () => {
    try {
      await getHealth();
      set({ backendReady: true });
      await get().syncEngineState();
      return;
    } catch {
      // continue to auto-start below
    }

    if (!isTauriRuntime()) {
      set({ backendReady: false, engineDesired: false });
      useSystemStore.setState({ status: null, health: null, error: null });
      return;
    }

    set({ starting: true, error: null });
    try {
      let launcherError: Error | null = null;
      const launcherPromise = invoke("start_cerebro_backend").catch((err) => {
        launcherError = toError(err);
      });
      await waitForBackend(() => launcherError);
      void launcherPromise;
      set({ backendReady: true });
      await get().syncEngineState();
    } catch (e) {
      set({
        backendReady: false,
        engineDesired: false,
        error: toError(e).message,
      });
      useSystemStore.setState({ status: null, health: null, error: null });
    } finally {
      set({ starting: false });
    }
  },

  turnOn: async () => {
    set({ starting: true, error: null });
    try {
      if (!get().backendReady) {
        await get().probeBackend();
      }
      if (!get().backendReady) {
        throw new Error("Cerebro backend is offline");
      }

      if (isTauriRuntime()) {
        try {
          await startEngine();
        } catch {
          await invoke("start_cerebro_engine");
          await waitForEngineRunning();
        }
      } else {
        throw new Error("Start engine from Terminal: make engine");
      }

      set({ engineDesired: true });
      await useSystemStore.getState().refresh();
      await get().syncEngineState();
    } catch (e) {
      set({ error: toError(e).message });
    } finally {
      set({ starting: false });
    }
  },

  turnOff: async () => {
    set({ stopping: true, error: null });
    try {
      if (!get().backendReady) {
        throw new Error("Cerebro backend is offline");
      }
      if (isTauriRuntime()) {
        await stopEngine();
      } else {
        throw new Error("Stop engine from Terminal: make desktop-stop-engine");
      }
      set({ engineDesired: false });
      await useSystemStore.getState().refresh();
      await get().syncEngineState();
    } catch (e) {
      set({ error: toError(e).message });
    } finally {
      set({ stopping: false });
    }
  },
}));

/** True when local llama.cpp engine is required for LLM chat (not Claude / MLX). */
export function needsLocalEngine(provider: string | undefined): boolean {
  return provider !== "claude" && provider !== "mlx";
}
