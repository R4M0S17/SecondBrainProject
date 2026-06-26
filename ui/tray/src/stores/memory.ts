import { create } from "zustand";
import {
  createMemoryEpisode,
  deleteMemoryEpisode,
  getMemorySession,
  listMemoryEpisodes,
  patchMemoryEpisode,
  recallMemory,
} from "../api/client";
import type {
  MemoryBrowserStats,
  MemoryEpisode,
  MemoryRecallResult,
  MemorySessionContext,
} from "../api/types";

export type MemoryFilter = "all" | "pinned" | "session" | "academic" | "code";

function formatLoadError(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e);
  if (msg.includes("404") || msg.includes("Not Found")) {
    return "stale_backend";
  }
  if (msg.includes("503")) {
    return "unavailable";
  }
  if (msg.includes("Request failed") || msg.includes("fetch")) {
    return "offline";
  }
  return msg;
}

const EMPTY_SESSION: MemorySessionContext = {
  session_summary: "",
  working_memory: {},
  last_consolidation_at: null,
  messages_in_short_term: 0,
};

const EMPTY_STATS: MemoryBrowserStats = {
  episodes_stored: 0,
  recall_hits_session: 0,
  queries_with_recall: 0,
  context_memory_pct: 0,
};

interface MemoryState {
  episodes: MemoryEpisode[];
  session: MemorySessionContext;
  stats: MemoryBrowserStats;
  loading: boolean;
  error: string | null;
  errorCode: "stale_backend" | "unavailable" | "offline" | null;
  usingMock: boolean;
  refresh: () => Promise<void>;
  addEpisode: (content: string, tags?: string[]) => Promise<void>;
  updateEpisode: (id: string, content: string, tags: string[]) => Promise<void>;
  deleteEpisode: (id: string) => Promise<void>;
  togglePin: (id: string) => Promise<void>;
  searchRecall: (query: string) => Promise<MemoryRecallResult[]>;
  episodeCount: () => number;
  clearError: () => void;
}

export const useMemoryStore = create<MemoryState>((set, get) => ({
  episodes: [],
  session: EMPTY_SESSION,
  stats: EMPTY_STATS,
  loading: false,
  error: null,
  errorCode: null,
  usingMock: false,

  episodeCount: () => get().stats.episodes_stored,

  clearError: () => set({ error: null, errorCode: null }),

  refresh: async () => {
    set({ loading: true, error: null, errorCode: null });
    try {
      const [episodesRes, session] = await Promise.all([
        listMemoryEpisodes(),
        getMemorySession(),
      ]);
      set({
        episodes: episodesRes.episodes,
        stats: episodesRes.stats,
        session,
        loading: false,
        usingMock: false,
      });
    } catch (e) {
      const code = formatLoadError(e);
      set({
        loading: false,
        error: code === "stale_backend" || code === "unavailable" || code === "offline" ? code : (e instanceof Error ? e.message : "Failed to load memory"),
        errorCode: code === "stale_backend" || code === "unavailable" || code === "offline" ? code : null,
        usingMock: false,
      });
    }
  },

  addEpisode: async (content, tags = ["manual"]) => {
    const trimmed = content.trim();
    if (!trimmed) return;
    set({ error: null });
    try {
      await createMemoryEpisode(trimmed, tags);
      await get().refresh();
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to add memory" });
      throw e;
    }
  },

  updateEpisode: async (id, content, tags) => {
    set({ error: null });
    try {
      await patchMemoryEpisode(id, { content, tags });
      await get().refresh();
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to update memory" });
      throw e;
    }
  },

  deleteEpisode: async (id) => {
    set({ error: null });
    try {
      await deleteMemoryEpisode(id);
      await get().refresh();
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to delete memory" });
      throw e;
    }
  },

  togglePin: async (id) => {
    const episode = get().episodes.find((e) => e.id === id);
    if (!episode) return;
    set({ error: null });
    try {
      await patchMemoryEpisode(id, { pinned: !episode.pinned });
      await get().refresh();
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to update memory" });
      throw e;
    }
  },

  searchRecall: async (query) => {
    const q = query.trim();
    if (!q) return [];
    const res = await recallMemory(q);
    return res.results;
  },
}));
