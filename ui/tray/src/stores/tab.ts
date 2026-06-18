import { create } from "zustand";

export type LeftTab = "chat" | "tools" | "code" | "sources";

interface TabState {
  activeTab: LeftTab;
  setTab: (tab: LeftTab) => void;
  scratch: string;
  setScratch: (v: string) => void;
}

export const useTabStore = create<TabState>((set) => ({
  activeTab: "chat",
  setTab: (tab) => set({ activeTab: tab }),
  scratch: "",
  setScratch: (v) => set({ scratch: v }),
}));
