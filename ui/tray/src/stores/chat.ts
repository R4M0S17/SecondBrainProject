import { create } from "zustand";
import type { ResponseMetadata, AgentId, ToolCallRecord } from "../api/types";
import { useToolOutputStore } from "./toolOutput";
import type { StoredToolCall } from "./toolOutput";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata?: ResponseMetadata;
  timestamp: number;
  expandedPanel?: "sources" | "tools" | "memory" | null;
}

export interface PendingChatAction {
  query: string;
  autoSend: boolean;
  agentId?: AgentId;
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

export interface SearchingSources {
  count: number;
  sources: string[];
}

interface ChatState {
  messages: Message[];
  isLoading: boolean;
  abortController: AbortController | null;
  activeAgent: AgentId;
  /** Durable session key — same as API ``conversation_id`` for this chat surface. */
  conversationId: string | null;
  /** User-visible conversation title (editable). */
  conversationTitle: string;
  pendingConfirmation: PendingConfirmation | null;
  searchingSources: SearchingSources | null;
  searchingWeb: boolean;
  pendingChatAction: PendingChatAction | null;

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
  setSearchingSources: (s: SearchingSources | null) => void;
  setSearchingWeb: (s: boolean) => void;
  setPendingChatAction: (action: PendingChatAction | null) => void;
  consumePendingChatAction: () => PendingChatAction | null;
  renameConversation: (title: string) => void;
}

function genId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function defaultTitle(messages: Message[]): string {
  const firstUser = messages.find((m) => m.role === "user");
  if (!firstUser) return "";
  const text = firstUser.content.trim();
  return text.length > 60 ? text.slice(0, 60) + "…" : text;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isLoading: false,
  abortController: null,
  activeAgent: "auto",
  conversationId: null,
  conversationTitle: "",
  pendingConfirmation: null,
  searchingSources: null,
  searchingWeb: false,
  pendingChatAction: null,

  addMessage: (msg) => {
    const id = genId();
    set((state) => {
      const newMsg = { ...msg, id, timestamp: Date.now(), expandedPanel: null };
      const messages = [...state.messages, newMsg];
      const title = state.conversationTitle || (msg.role === "user" ? defaultTitle(messages) : "");
      return { messages, conversationTitle: title };
    });
    return id;
  },

  updateMessage: (id, patch) => {
    set((state) => {
      const messages = state.messages.map((m) =>
        m.id === id ? { ...m, ...patch } : m
      );
      if (patch.metadata?.tools_called?.length) {
        const convId = state.conversationId ?? "unknown";
        const msgIdx = messages.findIndex((m) => m.id === id);
        const stored: StoredToolCall[] = patch.metadata.tools_called.map(
          (tc: ToolCallRecord, tci: number) => ({
            ...tc,
            id: `${convId}-${msgIdx}-${tci}`,
            conversationId: convId,
            storedAt: new Date().toISOString(),
          })
        );
        useToolOutputStore.getState().addCalls(stored);
      }
      return { messages };
    });
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

  setSearchingSources: (s) => set({ searchingSources: s }),
  setSearchingWeb: (s) => set({ searchingWeb: s }),

  setPendingChatAction: (action) => set({ pendingChatAction: action }),

  consumePendingChatAction: () => {
    const action = get().pendingChatAction;
    if (action) set({ pendingChatAction: null });
    return action;
  },

  renameConversation: (title) => set({ conversationTitle: title }),

  clearMessages: () => set({ messages: [], conversationId: null, conversationTitle: "", searchingSources: null, searchingWeb: false, pendingChatAction: null }),
}));
