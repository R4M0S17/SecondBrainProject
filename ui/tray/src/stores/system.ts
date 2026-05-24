import { create } from "zustand";
import type { StatusResponse, HealthResponse, FleetStatus, ModelSwapEvent } from "../api/types";
import { getStatus, getHealth, getFleetStatus } from "../api/client";

interface SystemState {
  status: StatusResponse | null;
  health: HealthResponse | null;
  fleetStatus: FleetStatus | null;
  swapEvent: ModelSwapEvent | null;
  lastRefreshed: number | null;
  error: string | null;
  pollingInterval: ReturnType<typeof setInterval> | null;

  refresh: () => Promise<void>;
  refreshFleet: () => Promise<void>;
  setSwapEvent: (event: ModelSwapEvent | null) => void;
  startPolling: (intervalMs?: number) => void;
  stopPolling: () => void;
}

export const useSystemStore = create<SystemState>((set, get) => ({
  status: null,
  health: null,
  fleetStatus: null,
  swapEvent: null,
  lastRefreshed: null,
  error: null,
  pollingInterval: null,

  refresh: async () => {
    try {
      const [status, health] = await Promise.all([getStatus(), getHealth()]);
      set({ status, health, lastRefreshed: Date.now(), error: null });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Unknown error" });
    }
  },

  refreshFleet: async () => {
    try {
      const fleetStatus = await getFleetStatus();
      set({ fleetStatus });
    } catch {
      // fleet endpoint may not exist yet; fail silently
    }
  },

  setSwapEvent: (event) => set({ swapEvent: event }),

  startPolling: (intervalMs = 10_000) => {
    const { pollingInterval, refresh, refreshFleet } = get();
    if (pollingInterval) return; // already polling
    refresh();
    refreshFleet();
    const id = setInterval(() => {
      get().refresh();
      get().refreshFleet();
    }, intervalMs);
    set({ pollingInterval: id });
  },

  stopPolling: () => {
    const { pollingInterval } = get();
    if (pollingInterval) {
      clearInterval(pollingInterval);
      set({ pollingInterval: null });
    }
  },
}));

export function selectIsClaudeMode(status: StatusResponse | null): boolean {
  return status?.provider === "claude";
}

export function selectRamPressure(
  status: StatusResponse | null,
): "ok" | "warn" | "critical" {
  return status?.ram_pressure ?? "ok";
}

export function selectSwapInProgress(state: SystemState): boolean {
  return state.fleetStatus?.swap_in_progress ?? false;
}

export function selectLlamaServerState(
  state: SystemState,
): "up" | "restarting" | "down" | null {
  return state.health?.llama_server ?? null;
}
