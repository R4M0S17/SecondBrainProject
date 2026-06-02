import { create } from "zustand";
import { invoke } from "@tauri-apps/api/core";
import { isTauriRuntime } from "../lib/tauri";
import { getHealth } from "../api/client";
import { useSystemStore } from "./system";

interface ServicesState {
  starting: boolean;
  stopping: boolean;
  /** User-facing backend state; default off in the desktop app. */
  servicesOff: boolean;
  error: string | null;
  probeBackend: () => Promise<void>;
  turnOn: () => Promise<void>;
  turnOff: () => Promise<void>;
  clearError: () => void;
}

const HEALTH_POLL_MS = 2000;
const HEALTH_POLL_MAX = 90;
const HEALTH_REQUEST_TIMEOUT_MS = 4000;

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : String(error));
}

async function getHealthWithTimeout(): Promise<void> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), HEALTH_REQUEST_TIMEOUT_MS);
  try {
    await getHealth(controller.signal);
  } finally {
    clearTimeout(timeout);
  }
}

async function waitForBackend(getLauncherError?: () => Error | null): Promise<void> {
  for (let i = 0; i < HEALTH_POLL_MAX; i++) {
    const launcherError = getLauncherError?.();
    if (launcherError) {
      throw launcherError;
    }
    try {
      await getHealthWithTimeout();
      return;
    } catch {
      await new Promise((r) => setTimeout(r, HEALTH_POLL_MS));
    }
  }
  const launcherError = getLauncherError?.();
  if (launcherError) {
    throw launcherError;
  }
  throw new Error("Backend did not respond in time. See ~/.cerebro/logs/");
}

export const useServicesStore = create<ServicesState>((set) => ({
  starting: false,
  stopping: false,
  servicesOff: isTauriRuntime(),
  error: null,

  clearError: () => set({ error: null }),

  probeBackend: async () => {
    try {
      await getHealthWithTimeout();
      set({ servicesOff: false });
      await useSystemStore.getState().refresh();
    } catch {
      set({ servicesOff: isTauriRuntime() });
      useSystemStore.setState({ status: null, health: null, error: null });
    }
  },

  turnOn: async () => {
    set({ starting: true, error: null });
    try {
      if (!isTauriRuntime()) {
        throw new Error("Turn on from Terminal: make desktop-launch");
      }
      let launcherError: Error | null = null;
      const launcherPromise = invoke("restart_cerebro_services").catch((err) => {
        launcherError = toError(err);
      });
      await waitForBackend(() => launcherError);
      void launcherPromise;
      void useSystemStore.getState().refresh();
      set({ servicesOff: false });
    } catch (e) {
      set({ error: toError(e).message });
    } finally {
      set({ starting: false });
    }
  },

  turnOff: async () => {
    set({ stopping: true, error: null });
    try {
      if (!isTauriRuntime()) {
        throw new Error("Turn off from Terminal: make desktop-stop");
      }
      await invoke("stop_cerebro_services");
      useSystemStore.setState({ status: null, health: null, error: null });
      set({ servicesOff: true });
    } catch (e) {
      set({ error: toError(e).message });
    } finally {
      set({ stopping: false });
    }
  },
}));
