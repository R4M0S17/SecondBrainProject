import { describe, it, expect, beforeEach } from "vitest";
import { useWizardStore } from "./wizard";

beforeEach(() => {
  useWizardStore.setState({ currentStep: -1, mode: null, isComplete: false, isQuickMode: false });
});

describe("useWizardStore", () => {
  it("starts at step -1 (welcome)", () => {
    expect(useWizardStore.getState().currentStep).toBe(-1);
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

  it("advances from welcome to backend in advanced mode", () => {
    useWizardStore.getState().setQuickMode(false);
    useWizardStore.getState().advance();
    expect(useWizardStore.getState().currentStep).toBe(0);
  });

  it("advances from welcome to folders in quick mode", () => {
    useWizardStore.getState().setQuickMode(true);
    useWizardStore.getState().advance();
    expect(useWizardStore.getState().currentStep).toBe(3);
  });

  it("advances from step 0 to step 1 in local mode", () => {
    useWizardStore.getState().setQuickMode(false);
    useWizardStore.getState().setMode("local");
    useWizardStore.getState().advance(); // -1 -> 0
    useWizardStore.getState().advance(); // 0 -> 1
    expect(useWizardStore.getState().currentStep).toBe(1);
  });

  it("advances from step 0 to step 3 in claude mode (skip local steps)", () => {
    useWizardStore.getState().setQuickMode(false);
    useWizardStore.getState().setMode("claude");
    useWizardStore.getState().advance(); // -1 -> 0
    useWizardStore.getState().advance(); // 0 -> 3
    expect(useWizardStore.getState().currentStep).toBe(3);
  });

  it("advances through all steps and completes", () => {
    useWizardStore.getState().setQuickMode(false);
    useWizardStore.getState().setMode("local");
    useWizardStore.getState().advance(); // -1 -> 0
    useWizardStore.getState().advance(); // 0 -> 1
    expect(useWizardStore.getState().currentStep).toBe(1);
    expect(useWizardStore.getState().isComplete).toBe(false);
    useWizardStore.getState().advance(); // 1 -> 2
    expect(useWizardStore.getState().currentStep).toBe(2);
    useWizardStore.getState().advance(); // 2 -> 3
    expect(useWizardStore.getState().currentStep).toBe(3);
    useWizardStore.getState().advance(); // 3 -> complete
    expect(useWizardStore.getState().isComplete).toBe(true);
  });

  it("quick mode completes after folders", () => {
    useWizardStore.getState().setQuickMode(true);
    useWizardStore.getState().advance(); // -1 -> 3
    expect(useWizardStore.getState().currentStep).toBe(3);
    useWizardStore.getState().advance(); // 3 -> complete
    expect(useWizardStore.getState().isComplete).toBe(true);
  });

  it("completes the wizard directly", () => {
    useWizardStore.getState().complete();
    expect(useWizardStore.getState().isComplete).toBe(true);
  });

  it("resets to initial state", () => {
    useWizardStore.getState().setQuickMode(false);
    useWizardStore.getState().setMode("local");
    useWizardStore.getState().advance();
    useWizardStore.getState().advance();
    useWizardStore.getState().reset();
    expect(useWizardStore.getState().currentStep).toBe(-1);
    expect(useWizardStore.getState().mode).toBeNull();
    expect(useWizardStore.getState().isComplete).toBe(false);
    expect(useWizardStore.getState().isQuickMode).toBe(false);
  });
});
