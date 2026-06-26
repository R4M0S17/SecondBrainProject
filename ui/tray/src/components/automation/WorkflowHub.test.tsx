import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import WorkflowHub from "./WorkflowHub";
import { useWorkflowStore } from "../../stores/workflows";
import type { Workflow } from "../../api/types";
import * as client from "../../api/client";

vi.mock("../../api/client", () => ({
  listWorkflows: vi.fn().mockResolvedValue([]),
  getWorkflow: vi.fn(),
  deleteWorkflow: vi.fn(),
  runWorkflow: vi.fn(),
  listWorkflowRuns: vi.fn().mockResolvedValue([]),
  startWorkflowRecording: vi.fn(),
  getWorkflowRecordingStatus: vi.fn(),
  stopWorkflowRecording: vi.fn(),
  cancelWorkflowRecording: vi.fn(),
  updateWorkflow: vi.fn(),
  listRecipeTemplates: vi.fn().mockResolvedValue([]),
  installRecipe: vi.fn(),
}));

const sampleWorkflow: Workflow = {
  id: "wf-1",
  name: "Export Screenshots",
  description: "Moves PNG files",
  workflow_type: "desktop",
  applescript: 'display dialog "hi"',
  parameters: [],
  steps: [
    { order: 1, app: "Finder", action: "Activate Finder", detail: "" },
  ],
  tags: [],
  created_at: 1_700_000_000,
  updated_at: 1_700_000_000,
  run_count: 5,
  last_run: 1_700_100_000,
};

describe("WorkflowHub", () => {
  beforeEach(() => {
    vi.mocked(client.listWorkflows).mockResolvedValue([]);
    useWorkflowStore.setState({
      workflows: [],
      selectedId: null,
      selected: null,
      isLoading: false,
      runResult: null,
      error: null,
      searchQuery: "",
      recordingStatus: null,
      isRecording: false,
      isGeneralizing: false,
      openCreateMode: null,
    });
  });

  it("renders empty state when no workflows", () => {
    render(<WorkflowHub />);
    expect(screen.getByText("Create your first routine")).toBeInTheDocument();
    expect(screen.getByText("Record routine")).toBeInTheDocument();
  });

  it("renders workflow list", async () => {
    vi.mocked(client.listWorkflows).mockResolvedValue([sampleWorkflow]);
    render(<WorkflowHub />);
    await waitFor(() => {
      expect(screen.getByText("Export Screenshots")).toBeInTheDocument();
    });
  });

  it("shows detail when workflow is selected", async () => {
    vi.mocked(client.listWorkflows).mockResolvedValue([sampleWorkflow]);
    vi.mocked(client.getWorkflow).mockResolvedValue(sampleWorkflow);
    useWorkflowStore.setState({
      workflows: [sampleWorkflow],
      selectedId: "wf-1",
      selected: sampleWorkflow,
    });
    render(<WorkflowHub />);
    await waitFor(() => {
      expect(screen.getByText("Activate Finder")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Run" })).toBeInTheDocument();
  });

  it("filters workflows by search query", async () => {
    const other: Workflow = { ...sampleWorkflow, id: "wf-2", name: "Organize Desktop" };
    vi.mocked(client.listWorkflows).mockResolvedValue([sampleWorkflow, other]);
    useWorkflowStore.setState({ workflows: [sampleWorkflow, other], searchQuery: "export" });
    render(<WorkflowHub />);
    await waitFor(() => {
      expect(screen.getByText("Export Screenshots")).toBeInTheDocument();
    });
    expect(screen.queryByText("Organize Desktop")).not.toBeInTheDocument();
  });

  it("selects workflow from list click", async () => {
    const select = vi.fn().mockResolvedValue(undefined);
    vi.mocked(client.listWorkflows).mockResolvedValue([sampleWorkflow]);
    useWorkflowStore.setState({
      workflows: [sampleWorkflow],
      select,
    });
    render(<WorkflowHub />);
    await waitFor(() => {
      expect(screen.getByText("Export Screenshots")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Export Screenshots"));
    expect(select).toHaveBeenCalledWith("wf-1");
  });
});
