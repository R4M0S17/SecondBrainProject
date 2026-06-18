import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import MessageBubble from "./MessageBubble";
import { useChatStore } from "../../stores/chat";
import type { Message } from "../../stores/chat";

function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: "msg-1",
    role: "user",
    content: "Hello",
    timestamp: Date.now(),
    expandedPanel: null,
    ...overrides,
  };
}

function renderInStore(component: React.ReactElement) {
  return render(component);
}

describe("MessageBubble", () => {
  it("renders user message on the right", () => {
    const msg = makeMessage({ role: "user", content: "Hi there" });
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Hi there")).toBeInTheDocument();
    expect(screen.getByLabelText("Your message")).toBeInTheDocument();
  });

  it("renders assistant message on the left", () => {
    const msg = makeMessage({ role: "assistant", content: "Hello from AI" });
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Hello from AI")).toBeInTheDocument();
    expect(screen.getByLabelText("Assistant message")).toBeInTheDocument();
  });

  it("shows cursor when streaming", () => {
    const msg = makeMessage({ role: "assistant", content: "Thinking" });
    const { container } = render(<MessageBubble message={msg} isStreaming />);
    const cursor = container.querySelector(".animate-pulse");
    expect(cursor).toBeInTheDocument();
  });

  it("renders searching indicator when searching sources", () => {
    useChatStore.setState({
      searchingSources: { count: 5, sources: ["a.md", "b.txt", "c.py", "d.json", "e.yaml"] },
    });
    const msg = makeMessage({ role: "assistant", content: "" });
    render(<MessageBubble message={msg} />);
    expect(screen.getByText(/Searching 5 files…/)).toBeInTheDocument();
  });

  it("renders searching web indicator", () => {
    useChatStore.setState({ searchingWeb: true, searchingSources: null });
    const msg = makeMessage({ role: "assistant", content: "" });
    render(<MessageBubble message={msg} />);
    expect(screen.getByText(/Searching the web…/)).toBeInTheDocument();
  });
});
