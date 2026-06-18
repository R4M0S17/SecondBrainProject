import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import WarningToast from "./WarningToast";

describe("WarningToast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders warning message", () => {
    render(<WarningToast message="Test warning" />);
    expect(screen.getByText("Test warning")).toBeInTheDocument();
  });

  it("calls onDismiss after 6 seconds", () => {
    const onDismiss = vi.fn();
    render(<WarningToast message="Auto dismiss" onDismiss={onDismiss} />);
    act(() => {
      vi.advanceTimersByTime(6000);
    });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("disappears after 6 seconds", () => {
    render(<WarningToast message="Auto dismiss" />);
    expect(screen.getByText("Auto dismiss")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(6000);
    });
    expect(screen.queryByText("Auto dismiss")).not.toBeInTheDocument();
  });

  it("calls onDismiss on manual dismiss", () => {
    const onDismiss = vi.fn();
    render(<WarningToast message="Dismiss me" onDismiss={onDismiss} />);
    fireEvent.click(screen.getByLabelText("Dismiss warning"));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("has role alert", () => {
    render(<WarningToast message="Alert" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
