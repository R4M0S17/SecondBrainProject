import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import OutputTab from "./OutputTab";
import { useToolOutputStore } from "../../stores/toolOutput";

beforeEach(() => {
  useToolOutputStore.setState({ calls: [] });
});

describe("OutputTab", () => {
  it("shows empty state when no tools called", () => {
    render(<OutputTab />);
    expect(screen.getByText("No tools executed yet")).toBeInTheDocument();
  });

  it("shows tool calls from the store", () => {
    useToolOutputStore.getState().addCalls([
      {
        id: "conv-0-0",
        name: "execute_python",
        args_summary: '{"code": "print(1)"}',
        result_summary: "1",
        latency_ms: 150,
        approved: true,
        conversationId: "conv",
        storedAt: new Date().toISOString(),
      },
    ]);
    render(<OutputTab />);
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getAllByText("Executed").length).toBeGreaterThanOrEqual(1);
  });

  it("filter denied shows only denied calls", () => {
    useToolOutputStore.getState().addCalls([
      {
        id: "conv-0-0",
        name: "write_file",
        args_summary: "{}",
        result_summary: "ok",
        latency_ms: 100,
        approved: true,
        conversationId: "conv",
        storedAt: new Date().toISOString(),
      },
      {
        id: "conv-0-1",
        name: "delete_file",
        args_summary: "{}",
        result_summary: "denied",
        latency_ms: 50,
        approved: false,
        conversationId: "conv",
        storedAt: new Date().toISOString(),
      },
    ]);
    render(<OutputTab />);
    const deniedBtn = screen.getByRole("button", { name: "Denied" });
    fireEvent.click(deniedBtn);
    expect(screen.getByText("Delete File")).toBeInTheDocument();
    expect(screen.queryByText("Write File")).not.toBeInTheDocument();
  });

  it("search filters by tool name", () => {
    useToolOutputStore.getState().addCalls([
      {
        id: "conv-0-0",
        name: "execute_python",
        args_summary: "{}",
        result_summary: "42",
        latency_ms: 100,
        approved: true,
        conversationId: "conv",
        storedAt: new Date().toISOString(),
      },
      {
        id: "conv-0-1",
        name: "write_file",
        args_summary: "{}",
        result_summary: "ok",
        latency_ms: 100,
        approved: true,
        conversationId: "conv",
        storedAt: new Date().toISOString(),
      },
    ]);
    render(<OutputTab />);
    const searchInput = screen.getByPlaceholderText("Search tool…");
    fireEvent.change(searchInput, { target: { value: "python" } });
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.queryByText("Write File")).not.toBeInTheDocument();
  });

  it("expand/collapse toggles full content", () => {
    const longResult = "x".repeat(400);
    useToolOutputStore.getState().addCalls([
      {
        id: "conv-0-0",
        name: "run_script",
        args_summary: "{}",
        result_summary: longResult,
        latency_ms: 200,
        approved: true,
        conversationId: "conv",
        storedAt: new Date().toISOString(),
      },
    ]);
    render(<OutputTab />);
    const expandBtn = screen.getByText("Show more");
    fireEvent.click(expandBtn);
    expect(screen.getByText("Show less")).toBeInTheDocument();
  });
});
