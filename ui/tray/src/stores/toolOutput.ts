import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ToolCallRecord } from "../api/types";

export interface StoredToolCall extends ToolCallRecord {
  id: string;
  conversationId: string;
  storedAt: string;
}

interface ToolOutputState {
  calls: StoredToolCall[];
  addCalls: (calls: StoredToolCall[]) => void;
  clear: () => void;
}

export const useToolOutputStore = create<ToolOutputState>()(
  persist(
    (set) => ({
      calls: [],
      addCalls: (newCalls) =>
        set((s) => {
          const existingIds = new Set(s.calls.map((c) => c.id));
          const fresh = newCalls.filter((c) => !existingIds.has(c.id));
          const merged = [...s.calls, ...fresh];
          return { calls: merged.slice(-500) };
        }),
      clear: () => set({ calls: [] }),
    }),
    {
      name: "cerebro-tool-output",
      partialize: (state) => ({ calls: state.calls }),
    }
  )
);
