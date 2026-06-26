import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import EngineIndicator from "./EngineIndicator";

describe("EngineIndicator", () => {
  it("shows backend offline when backendReady is false", () => {
    render(<EngineIndicator ok={false} backendReady={false} />);
    expect(screen.getByText("Cerebro offline")).toBeInTheDocument();
  });

  it("shows engine off when backend is up but engine is down", () => {
    render(<EngineIndicator ok={false} backendReady provider="llamacpp" llamaServer="down" />);
    expect(screen.getByText("off")).toBeInTheDocument();
  });

  it("shows Claude API label for claude provider", () => {
    render(<EngineIndicator ok={true} backendReady provider="claude" />);
    expect(screen.getByText("Claude API")).toBeInTheDocument();
  });
});
