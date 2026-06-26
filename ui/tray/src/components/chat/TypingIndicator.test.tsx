import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TypingIndicator from "./TypingIndicator";

describe("TypingIndicator", () => {
  it("renders with default model name", () => {
    render(<TypingIndicator />);
    expect(screen.getByText(/Thinking with local/)).toBeInTheDocument();
  });

  it("renders with custom model name", () => {
    render(<TypingIndicator model="Qwen3.5-2B" />);
    expect(screen.getByText(/Thinking with Qwen3.5-2B/)).toBeInTheDocument();
  });

  it("has aria-live polite", () => {
    render(<TypingIndicator />);
    expect(screen.getByLabelText("Thinking with local")).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });

  it("renders timer and progress bar", () => {
    render(<TypingIndicator />);
    expect(screen.getByText(/0s/)).toBeInTheDocument();
  });
});
