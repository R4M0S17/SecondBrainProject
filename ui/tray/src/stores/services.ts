import { create } from "zustand";
import { invoke } from "@tauri-apps/api/core";
import { isTauriRuntime } from "../lib/tauri";
import { getHealth } from "../api/client";
import { useSystemStore } from "./system";

interface ServicesState {
  starting: boolean;
  stopping: boolean;
  error: string | null;
  turnOn: () => Promise<void>;
  turnOff: () => Promise<void>;
  clearError: () => void;
}

const HEALTH_POLL_MS = 2000;
const HEALTH_POLL_MAX = 90;

async function waitForBackend(): Promise<void> {
  for (let i = 0; i < HEALTH_POLL_MAX; i++) {
    try {
      await getHealth();
      return;
    } catch {
      await new Promise((r) => setTimeout(r, HEALTH_POLL_MS));
    }
  }
  throw new Error("Backend did not respond in time. See ~/.cerebro/logs/");
}

export const useServicesStore = create<ServicesState>((set) => ({
  starting: false,
  stopping: false,
  error: null,

  clearError: () => set({ error: null }),

  turnOn: async () => {
    set({ starting: true, error: null });
    try {
      if (!isTauriRuntime()) {
        throw new Error("Turn on from Terminal: make desktop-launch");
      }
      await invoke("restart_cerebro_services");
      await waitForBackend();
      await useSystemStore.getState().refresh();
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
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
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    } finally {
      set({ stopping: false });
    }
  },
}));
