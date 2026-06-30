import { create } from "zustand";
import type { LeftTab } from "./tab";

interface NotificationState {
  badges: Partial<Record<LeftTab, number>>;
  increment: (tab: LeftTab) => void;
  clear: (tab: LeftTab) => void;
  clearAll: () => void;
}

export const useNotificationStore = create<NotificationState>((set) => ({
  badges: {},

  increment: (tab) =>
    set((state) => ({
      badges: {
        ...state.badges,
        [tab]: (state.badges[tab] ?? 0) + 1,
      },
    })),

  clear: (tab) =>
    set((state) => {
      const { [tab]: _, ...rest } = state.badges;
      return { badges: rest };
    }),

  clearAll: () => set({ badges: {} }),
}));
