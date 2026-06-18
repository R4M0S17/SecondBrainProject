import { describe, it, expect, beforeEach } from "vitest";
import { useChatStore } from "./chat";

beforeEach(() => {
  useChatStore.setState({
    messages: [],
    isLoading: false,
    abortController: null,
    activeAgent: "auto",
    conversationId: null,
    pendingConfirmation: null,
    searchingSources: null,
    searchingWeb: false,
  });
});

describe("useChatStore", () => {
  it("adds a message and returns its id", () => {
    const id = useChatStore.getState().addMessage({
      role: "user",
      content: "Hello",
    });
    expect(id).toBeTruthy();
    const { messages } = useChatStore.getState();
    expect(messages).toHaveLength(1);
    expect(messages[0].role).toBe("user");
    expect(messages[0].content).toBe("Hello");
    expect(messages[0].id).toBe(id);
    expect(messages[0].timestamp).toBeGreaterThan(0);
  });

  it("updates a message by id", () => {
    const id = useChatStore.getState().addMessage({
      role: "assistant",
      content: "Initial",
    });
    useChatStore.getState().updateMessage(id, { content: "Updated" });
    const msg = useChatStore.getState().messages.find((m) => m.id === id);
    expect(msg?.content).toBe("Updated");
  });

  it("appends tokens to a message", () => {
    const id = useChatStore.getState().addMessage({
      role: "assistant",
      content: "",
    });
    useChatStore.getState().appendToken(id, "Hel");
    useChatStore.getState().appendToken(id, "lo");
    const msg = useChatStore.getState().messages.find((m) => m.id === id);
    expect(msg?.content).toBe("Hello");
  });

  it("sets loading state", () => {
    useChatStore.getState().setLoading(true);
    expect(useChatStore.getState().isLoading).toBe(true);
    useChatStore.getState().setLoading(false);
    expect(useChatStore.getState().isLoading).toBe(false);
  });

  it("sets active agent", () => {
    useChatStore.getState().setActiveAgent("code");
    expect(useChatStore.getState().activeAgent).toBe("code");
  });

  it("cancels request aborts controller", () => {
    const ctrl = new AbortController();
    useChatStore.getState().setAbortController(ctrl);
    useChatStore.getState().cancelRequest();
    expect(ctrl.signal.aborted).toBe(true);
    expect(useChatStore.getState().abortController).toBeNull();
    expect(useChatStore.getState().isLoading).toBe(false);
  });

  it("toggles message panels", () => {
    const id = useChatStore.getState().addMessage({
      role: "assistant",
      content: "test",
    });
    useChatStore.getState().toggleMessagePanel(id, "sources");
    let msg = useChatStore.getState().messages.find((m) => m.id === id);
    expect(msg?.expandedPanel).toBe("sources");

    useChatStore.getState().toggleMessagePanel(id, "sources");
    msg = useChatStore.getState().messages.find((m) => m.id === id);
    expect(msg?.expandedPanel).toBeNull();
  });

  it("sets pending confirmation", () => {
    const conf = {
      toolName: "write_file",
      onApprove: () => {},
      onDeny: () => {},
    };
    useChatStore.getState().setPendingConfirmation(conf);
    expect(useChatStore.getState().pendingConfirmation?.toolName).toBe("write_file");
    useChatStore.getState().setPendingConfirmation(null);
    expect(useChatStore.getState().pendingConfirmation).toBeNull();
  });

  it("sets conversation id", () => {
    useChatStore.getState().setConversationId("conv-123");
    expect(useChatStore.getState().conversationId).toBe("conv-123");
  });

  it("clears messages", () => {
    useChatStore.getState().addMessage({ role: "user", content: "Hi" });
    useChatStore.getState().addMessage({ role: "assistant", content: "Hello" });
    useChatStore.getState().setConversationId("conv-1");
    useChatStore.getState().setSearchingSources({ count: 2, sources: ["a", "b"] });
    useChatStore.getState().setSearchingWeb(true);
    useChatStore.getState().clearMessages();
    const state = useChatStore.getState();
    expect(state.messages).toHaveLength(0);
    expect(state.conversationId).toBeNull();
    expect(state.searchingSources).toBeNull();
    expect(state.searchingWeb).toBe(false);
  });

  it("sets searching sources", () => {
    useChatStore.getState().setSearchingSources({ count: 3, sources: ["f1", "f2", "f3"] });
    expect(useChatStore.getState().searchingSources?.count).toBe(3);
    expect(useChatStore.getState().searchingSources?.sources).toEqual(["f1", "f2", "f3"]);
  });

  it("sets searching web", () => {
    useChatStore.getState().setSearchingWeb(true);
    expect(useChatStore.getState().searchingWeb).toBe(true);
    useChatStore.getState().setSearchingWeb(false);
    expect(useChatStore.getState().searchingWeb).toBe(false);
  });
});
