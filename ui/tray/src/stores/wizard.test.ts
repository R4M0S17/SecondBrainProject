import { describe, it, expect, beforeEach } from "vitest";
import { useWizardStore } from "./wizard";

beforeEach(() => {
  useWizardStore.setState({ currentStep: 0, mode: null, isComplete: false });
});

describe("useWizardStore", () => {
  it("starts at step 0", () => {
    expect(useWizardStore.getState().currentStep).toBe(0);
    expect(useWizardStore.getState().isComplete).toBe(false);
  });

  it("sets mode to local", () => {
    useWizardStore.getState().setMode("local");
    expect(useWizardStore.getState().mode).toBe("local");
  });

  it("sets mode to claude", () => {
    useWizardStore.getState().setMode("claude");
    expect(useWizardStore.getState().mode).toBe("claude");
  });

  it("advances from step 0 to step 1 in local mode", () => {
    useWizardStore.getState().setMode("local");
    useWizardStore.getState().advance();
    expect(useWizardStore.getState().currentStep).toBe(1);
  });

  it("advances from step 0 to step 3 in claude mode (skip local steps)", () => {
    useWizardStore.getState().setMode("claude");
    useWizardStore.getState().advance();
    expect(useWizardStore.getState().currentStep).toBe(3);
  });

  it("advances through all steps and completes", () => {
    useWizardStore.getState().setMode("local");
    useWizardStore.getState().advance();
    expect(useWizardStore.getState().currentStep).toBe(1);
    expect(useWizardStore.getState().isComplete).toBe(false);
    useWizardStore.getState().advance();
    expect(useWizardStore.getState().currentStep).toBe(2);
    useWizardStore.getState().advance();
    expect(useWizardStore.getState().currentStep).toBe(3);
    useWizardStore.getState().advance();
    expect(useWizardStore.getState().isComplete).toBe(true);
  });

  it("completes the wizard directly", () => {
    useWizardStore.getState().complete();
    expect(useWizardStore.getState().isComplete).toBe(true);
  });

  it("resets to initial state", () => {
    useWizardStore.getState().setMode("local");
    useWizardStore.getState().advance();
    useWizardStore.getState().advance();
    useWizardStore.getState().reset();
    expect(useWizardStore.getState().currentStep).toBe(0);
    expect(useWizardStore.getState().mode).toBeNull();
    expect(useWizardStore.getState().isComplete).toBe(false);
  });
});
