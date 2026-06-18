import { describe, it, expect, beforeEach, vi } from "vitest";
import { useToolsStore } from "./tools";
import * as client from "../api/client";

beforeEach(() => {
  useToolsStore.setState({ tools: [], loading: false, error: null });
});

describe("useToolsStore", () => {
  it("initial state is empty", () => {
    const s = useToolsStore.getState();
    expect(s.tools).toEqual([]);
    expect(s.loading).toBe(false);
    expect(s.error).toBeNull();
  });

  it("loads tools from API", async () => {
    const mockTools = [
      { name: "write_file", description: "Write files", required_permission: "write_file", requires_confirmation: true, scope: "filesystem", audit_level: "high", enabled: true, parameters: {} },
    ];
    const mockList = vi.spyOn(client, "listTools").mockResolvedValue(mockTools);
    await useToolsStore.getState().load();
    expect(useToolsStore.getState().tools).toEqual(mockTools);
    expect(useToolsStore.getState().loading).toBe(false);
    mockList.mockRestore();
  });

  it("handles load error", async () => {
    const mockList = vi.spyOn(client, "listTools").mockRejectedValue(new Error("Network error"));
    await useToolsStore.getState().load();
    expect(useToolsStore.getState().error).toBe("Network error");
    expect(useToolsStore.getState().loading).toBe(false);
    mockList.mockRestore();
  });

  it("toggles tool enabled state locally", async () => {
    useToolsStore.setState({
      tools: [{ name: "write_file", description: "Write", required_permission: "write_file", requires_confirmation: true, scope: "fs", audit_level: "high", enabled: true, parameters: {} }],
    });
    vi.spyOn(client, "getConfig").mockResolvedValue({
      model: "", watched_folders: [], tool_permissions: { execute_python: true, write_file: true, read_file: true, search_web: false },
      dnd_enabled: false, focus_mode: false, embedding_model: "", inference_backend: "llamacpp",
    });
    vi.spyOn(client, "updateConfig").mockResolvedValue({
      model: "", watched_folders: [], tool_permissions: { execute_python: true, write_file: true, read_file: true, search_web: false },
      dnd_enabled: false, focus_mode: false, embedding_model: "", inference_backend: "llamacpp",
    });
    await useToolsStore.getState().toggleTool("write_file", false);
    const tool = useToolsStore.getState().tools.find((t) => t.name === "write_file");
    expect(tool?.enabled).toBe(false);
    vi.restoreAllMocks();
  });
});
