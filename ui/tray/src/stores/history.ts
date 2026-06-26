import { create } from "zustand";
import {
  listConversations,
  getConversation,
  deleteConversation,
  searchConversations,
  batchDeleteConversations,
  batchPinConversations,
} from "../api/client";
import type { ConversationSummary, ConversationDetail } from "../api/types";

type HistoryTab = "list" | "detail";

interface HistoryState {
  conversations: ConversationSummary[];
  selected: ConversationDetail | null;
  loading: boolean;
  query: string;
  tab: HistoryTab;
  error: string | null;
  selectedIds: Set<string>;
  refresh: () => Promise<void>;
  search: (q: string) => Promise<void>;
  select: (id: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
  back: () => void;
  toggleSelect: (id: string) => void;
  selectAll: () => void;
  clearSelection: () => void;
  batchDelete: () => Promise<void>;
  batchPin: (pinned: boolean) => Promise<void>;
}

export const useHistoryStore = create<HistoryState>((set, get) => ({
  conversations: [],
  selected: null,
  loading: false,
  query: "",
  tab: "list",
  error: null,
  selectedIds: new Set(),

  refresh: async () => {
    set({ loading: true, error: null });
    try {
      const convs = await listConversations();
      set({ conversations: convs, loading: false, selectedIds: new Set() });
    } catch (e) {
      set({
        loading: false,
        error: e instanceof Error ? e.message : "Failed to load conversations",
      });
    }
  },

  search: async (q) => {
    set({ loading: true, error: null, query: q });
    try {
      const convs = await searchConversations(q);
      set({ conversations: convs, loading: false, selectedIds: new Set() });
    } catch (e) {
      set({
        loading: false,
        error: e instanceof Error ? e.message : "Search failed",
      });
    }
  },

  select: async (id) => {
    set({ loading: true, error: null });
    try {
      const detail = await getConversation(id);
      set({ selected: detail, tab: "detail", loading: false });
    } catch (e) {
      set({
        loading: false,
        error: e instanceof Error ? e.message : "Failed to load conversation",
      });
    }
  },

  remove: async (id) => {
    try {
      await deleteConversation(id);
      await get().refresh();
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to delete" });
    }
  },

  back: () => {
    set({ tab: "list", selected: null });
    void get().refresh();
  },

  toggleSelect: (id) => {
    const ids = new Set(get().selectedIds);
    if (ids.has(id)) ids.delete(id);
    else ids.add(id);
    set({ selectedIds: ids });
  },

  selectAll: () => {
    const ids = new Set(get().conversations.map((c) => c.conv_id));
    set({ selectedIds: ids });
  },

  clearSelection: () => {
    set({ selectedIds: new Set() });
  },

  batchDelete: async () => {
    const ids = Array.from(get().selectedIds);
    if (ids.length === 0) return;
    try {
      await batchDeleteConversations(ids);
      await get().refresh();
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to delete" });
    }
  },

  batchPin: async (pinned) => {
    const ids = Array.from(get().selectedIds);
    if (ids.length === 0) return;
    try {
      await batchPinConversations(ids, pinned);
      await get().refresh();
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : "Failed to update",
      });
    }
  },
}));
