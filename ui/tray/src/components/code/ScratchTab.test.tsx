import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ScratchTab from "./ScratchTab";
import { useTabStore } from "../../stores/tab";
import { useChatStore } from "../../stores/chat";

beforeEach(() => {
  useTabStore.setState({
    activeTab: "code",
    scratch: "",
    scratchLang: "plain",
  });
  useChatStore.setState({
    messages: [],
    isLoading: false,
    abortController: null,
    activeAgent: "auto",
    conversationId: null,
    pendingConfirmation: null,
    searchingSources: null,
    searchingWeb: false,
    pendingChatAction: null,
  });
});

describe("ScratchTab", () => {
  it("renders without crashing", () => {
    render(<ScratchTab />);
    expect(screen.getByText("Quick code scratchpad")).toBeInTheDocument();
  });

  it("send to agent button is disabled when scratch is empty", () => {
    render(<ScratchTab />);
    const btn = screen.getByText("Send to Agent");
    expect(btn).toBeDisabled();
  });

  it("send to agent button is enabled when scratch has content", () => {
    useTabStore.getState().setScratch("print('hello')");
    render(<ScratchTab />);
    const btn = screen.getByText("Send to Agent");
    expect(btn).not.toBeDisabled();
  });

  it("clicking send to agent sets pendingChatAction and navigates to chat", () => {
    useTabStore.getState().setScratch("print('hello')");
    render(<ScratchTab />);
    const btn = screen.getByText("Send to Agent");
    fireEvent.click(btn);
    const action = useChatStore.getState().pendingChatAction;
    expect(action).not.toBeNull();
    expect(action!.query).toContain("print('hello')");
    expect(action!.autoSend).toBe(true);
    expect(useTabStore.getState().activeTab).toBe("chat");
  });

  it("language selector buttons change scratchLang", () => {
    render(<ScratchTab />);
    const pythonBtn = screen.getByText("Python");
    fireEvent.click(pythonBtn);
    expect(useTabStore.getState().scratchLang).toBe("python");
  });

  it("⌘+Enter triggers send to agent", () => {
    useTabStore.getState().setScratch("const x = 1;");
    render(<ScratchTab />);
    const textarea = screen.getByRole("textbox");
    fireEvent.keyDown(textarea, { key: "Enter", metaKey: true });
    const action = useChatStore.getState().pendingChatAction;
    expect(action).not.toBeNull();
    expect(action!.query).toContain("const x = 1");
  });
});
