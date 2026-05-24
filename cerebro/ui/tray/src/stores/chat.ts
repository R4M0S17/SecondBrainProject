import { create } from "zustand";
import type { ResponseMetadata, AgentId } from "../api/types";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata?: ResponseMetadata;
  timestamp: number;
  expandedPanel?: "sources" | "tools" | "memory" | null;
}

export interface PendingConfirmation {
  toolName: string;
  toolPath?: string;
  toolAction?: string;
  toolSize?: string;
  warningText?: string;
  onApprove: () => void;
  onDeny: () => void;
}

interface ChatState {
  messages: Message[];
  isLoading: boolean;
  abortController: AbortController | null;
  activeAgent: AgentId;
  /** Durable session key — same as API ``conversation_id`` for this chat surface. */
  conversationId: string | null;
  pendingConfirmation: PendingConfirmation | null;

  addMessage: (msg: Omit<Message, "id" | "timestamp">) => string;
  updateMessage: (id: string, patch: Partial<Message>) => void;
  appendToken: (id: string, token: string) => void;
  setLoading: (loading: boolean) => void;
  setActiveAgent: (agent: AgentId) => void;
  cancelRequest: () => void;
  setAbortController: (ctrl: AbortController | null) => void;
  toggleMessagePanel: (id: string, panel: "sources" | "tools" | "memory") => void;
  setPendingConfirmation: (conf: PendingConfirmation | null) => void;
  setConversationId: (id: string | null) => void;
  clearMessages: () => void;
}

function genId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isLoading: false,
  abortController: null,
  activeAgent: "auto",
  conversationId: null,
  pendingConfirmation: null,

  addMessage: (msg) => {
    const id = genId();
    set((state) => ({
      messages: [
        ...state.messages,
        { ...msg, id, timestamp: Date.now(), expandedPanel: null },
      ],
    }));
    return id;
  },

  updateMessage: (id, patch) => {
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, ...patch } : m
      ),
    }));
  },

  appendToken: (id, token) => {
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, content: m.content + token } : m
      ),
    }));
  },

  setLoading: (loading) => set({ isLoading: loading }),

  setActiveAgent: (agent) => set({ activeAgent: agent }),

  cancelRequest: () => {
    const { abortController } = get();
    abortController?.abort();
    set({ abortController: null, isLoading: false });
  },

  setAbortController: (ctrl) => set({ abortController: ctrl }),

  toggleMessagePanel: (id, panel) => {
    set((state) => ({
      messages: state.messages.map((m) => {
        if (m.id !== id) return m;
        return { ...m, expandedPanel: m.expandedPanel === panel ? null : panel };
      }),
    }));
  },

  setPendingConfirmation: (conf) => set({ pendingConfirmation: conf }),

  setConversationId: (id) => set({ conversationId: id }),

  clearMessages: () => set({ messages: [], conversationId: null }),
}));
