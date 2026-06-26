import { create } from "zustand";

export type LeftTab = "home" | "chat" | "memory" | "tools" | "code" | "sources" | "workflows";

interface TabState {
  activeTab: LeftTab;
  setTab: (tab: LeftTab) => void;
  scratch: string;
  setScratch: (v: string) => void;
}

export const useTabStore = create<TabState>((set) => ({
  activeTab: "home",
  setTab: (tab) => set({ activeTab: tab }),
  scratch: "",
  setScratch: (v) => set({ scratch: v }),
}));
