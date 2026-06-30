import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TerminalTab from "./TerminalTab";

describe("TerminalTab", () => {
  it("renders without crashing", () => {
    render(<TerminalTab />);
    expect(screen.getByText("Loading terminal…")).toBeInTheDocument();
  });

  it("shows error UI when Tauri APIs are unavailable", async () => {
    render(<TerminalTab />);
    const errorTitle = await screen.findByText("Terminal failed to load", {}, { timeout: 10000 });
    expect(errorTitle).toBeInTheDocument();
  });

  it("does not have a Cmds dropdown", () => {
    render(<TerminalTab />);
    expect(screen.queryByText("Cmds")).not.toBeInTheDocument();
  });
});
