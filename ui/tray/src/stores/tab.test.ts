import { describe, it, expect, beforeEach } from "vitest";
import { useTabStore } from "./tab";

beforeEach(() => {
  useTabStore.setState({ activeTab: "chat", scratch: "" });
});

describe("useTabStore", () => {
  it("defaults to chat tab", () => {
    expect(useTabStore.getState().activeTab).toBe("chat");
  });

  it("sets active tab", () => {
    useTabStore.getState().setTab("code");
    expect(useTabStore.getState().activeTab).toBe("code");
    useTabStore.getState().setTab("memory");
    expect(useTabStore.getState().activeTab).toBe("memory");
  });

  it("stores scratch content", () => {
    useTabStore.getState().setScratch("console.log('hello')");
    expect(useTabStore.getState().scratch).toBe("console.log('hello')");
  });
});
