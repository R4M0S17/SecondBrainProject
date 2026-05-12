import { create } from "zustand";
import type { ConversationSummary, ConversationDetail } from "../api/types";
import { listConversations, getConversation } from "../api/client";

interface HistoryState {
  conversations: ConversationSummary[];
  activeConvId: string | null;
  activeConv: ConversationDetail | null;
  isLoading: boolean;

  loadList: () => Promise<void>;
  loadConversation: (id: string) => Promise<void>;
  setActiveConvId: (id: string | null) => void;
  clear: () => void;
}

export const useHistoryStore = create<HistoryState>((set) => ({
  conversations: [],
  activeConvId: null,
  activeConv: null,
  isLoading: false,

  loadList: async () => {
    set({ isLoading: true });
    try {
      const conversations = await listConversations();
      set({ conversations });
    } finally {
      set({ isLoading: false });
    }
  },

  loadConversation: async (id) => {
    set({ isLoading: true, activeConvId: id });
    try {
      const activeConv = await getConversation(id);
      set({ activeConv });
    } finally {
      set({ isLoading: false });
    }
  },

  setActiveConvId: (id) => set({ activeConvId: id, activeConv: null }),

  clear: () => set({ conversations: [], activeConvId: null, activeConv: null }),
}));
