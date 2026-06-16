import { create } from "zustand";
import { listTools, getConfig, updateConfig, type ToolInfo } from "../api/client";
import type { AppConfig } from "../api/types";

interface ToolsState {
  tools: ToolInfo[];
  loading: boolean;
  error: string | null;

  load: () => Promise<void>;
  toggleTool: (toolName: string, enabled: boolean) => Promise<void>;
}

const TOOL_PERM_MAP: Record<string, string> = {
  web_search: "search_web",
  write_file: "write_file",
  read_file: "read_file",
  execute_python: "execute_python",
  run_script: "execute_python",
  delete_file: "write_file",
  create_python_file: "write_file",
  create_calendar_event: "write_file",
  add_reminder: "write_file",
  delete_reminder: "write_file",
  create_directory: "write_file",
  create_note: "write_file",
};

export const useToolsStore = create<ToolsState>((set, get) => ({
  tools: [],
  loading: false,
  error: null,

  load: async () => {
    set({ loading: true, error: null });
    try {
      const tools = await listTools();
      set({ tools, loading: false });
    } catch (e) {
      set({
        loading: false,
        error: e instanceof Error ? e.message : "Failed to load tools",
      });
    }
  },

  toggleTool: async (toolName, enabled) => {
    const { tools } = get();
    set({
      tools: tools.map((t) =>
        t.name === toolName ? { ...t, enabled } : t
      ),
    });
    const permKey = TOOL_PERM_MAP[toolName];
    if (!permKey) return;
    try {
      const cfg = await getConfig();
      const perms = { ...cfg.tool_permissions, [permKey]: enabled } as AppConfig["tool_permissions"];
      await updateConfig({ tool_permissions: perms });
    } catch {
      await get().load();
    }
  },
}));
