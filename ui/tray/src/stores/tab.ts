import { create } from "zustand";
import { persist } from "zustand/middleware";

export type LeftTab = "home" | "chat" | "memory" | "code" | "sources" | "workflows";

export type ScratchLang = "python" | "shell" | "javascript" | "plain";

interface TabState {
  activeTab: LeftTab;
  setTab: (tab: LeftTab) => void;
  scratch: string;
  setScratch: (v: string) => void;
  scratchLang: ScratchLang;
  setScratchLang: (lang: ScratchLang) => void;
}

export const useTabStore = create<TabState>()(
  persist(
    (set) => ({
      activeTab: "home",
      setTab: (tab) => set({ activeTab: tab }),
      scratch: "",
      setScratch: (v) => set({ scratch: v }),
      scratchLang: "plain",
      setScratchLang: (lang) => set({ scratchLang: lang }),
    }),
    {
      name: "cerebro-tab-store",
      partialize: (state) => ({ scratch: state.scratch, scratchLang: state.scratchLang }),
    }
  )
);
