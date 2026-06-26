import { create } from "zustand";
import { getStatus, listConversations } from "../api/client";
import type { ConversationSummary, StatusResponse } from "../api/types";

const CACHE_KEY = "cerebro_dashboard_cache";

function loadCachedFiles(): number {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    return raw ? JSON.parse(raw) : 0;
  } catch { return 0; }
}

function saveCachedFiles(count: number) {
  try { localStorage.setItem(CACHE_KEY, JSON.stringify(count)); } catch {}
}

const FALLBACK_STATUS: StatusResponse = {
  indexed_files: loadCachedFiles(),
  engine_ok: false,
  model: "",
  provider: "",
  active_agent: "auto",
  ram_pressure: "ok",
  ram_total_gb: 0,
  ram_used_gb: 0,
  ram_available_gb: 0,
  cpu_percent: 0,
  queries_total: 0,
  avg_latency_ms: 0,
  p95_latency_ms: 0,
  tool_call_count: 0,
  memory_hits: 0,
  provider_fallbacks: 0,
};

export interface RecentActivity {
  id: string;
  label: string;
  description: string;
  timestamp: Date;
  icon: string;
  tab?: "chat" | "sources" | "tools" | "code";
}

interface DashboardState {
  status: StatusResponse | null;
  recentActivity: RecentActivity[];
  loading: boolean;
  error: string | null;
  quickNoteOpen: boolean;
  setQuickNoteOpen: (open: boolean) => void;
  pushActivity: (activity: RecentActivity) => void;
  refresh: () => Promise<void>;
}

function genActivityId(): string {
  return `activity-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  status: null,
  recentActivity: [],
  loading: true,
  error: null,
  quickNoteOpen: false,
  setQuickNoteOpen: (open) => set({ quickNoteOpen: open }),
  pushActivity: (activity) =>
    set((s) => ({
      recentActivity: [{ ...activity, id: genActivityId(), timestamp: new Date() }, ...s.recentActivity].slice(0, 20),
    })),

  refresh: async () => {
    set({ loading: true, error: null });
    try {
      const [status, conversations] = await Promise.all([
        getStatus(),
        listConversations().catch(() => [] as ConversationSummary[]),
      ]);

      const activity: RecentActivity[] = [];

      if (status.indexed_files > 0) {
        activity.push({
          id: "indexed",
          label: `Knowledge base: ${status.indexed_files} files indexed`,
          description: "Available for search and context",
          timestamp: new Date(),
          icon: "database",
          tab: "sources",
        });
      }

      for (const conv of conversations.slice(0, 5)) {
        activity.push({
          id: `conv-${conv.conv_id}`,
          label: conv.first_user_message ?? "Chat conversation",
          description: `Agent: ${conv.agent_id} · ${conv.message_count} messages`,
          timestamp: new Date(conv.last_active),
          icon: "chat",
          tab: "chat",
        });
      }

      saveCachedFiles(status.indexed_files);
      set({ status, recentActivity: activity, loading: false });
    } catch (e) {
      set({ status: { ...FALLBACK_STATUS, indexed_files: loadCachedFiles() }, loading: false });
    }
  },
}));
