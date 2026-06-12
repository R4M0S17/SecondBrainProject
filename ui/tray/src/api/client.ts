import { ApiError } from "./errors";
import type {
  ContextSourcesEvent,
  DocumentInfo,
  FileAttachment,
  QueryRequest,
  QueryResponse,
  ResponseMetadata,
  IndexResponse,
  IndexStatusResponse,
  StatusResponse,
  HealthResponse,
  WizardStatus,
  AppConfig,
  AgentId,
  ConversationSummary,
  ConversationDetail,
  ModelsResponse,
  LlamaCppModelsResponse,
  FleetStatus,
  FleetModelsResponse,
  ModelSwapEvent,
  DebugRun,
  DebugStep,
  DebugStepDetail,
  Workflow,
} from "./types";

export const AGENT_ID_MAP: Record<AgentId, string> = {
  auto:     "auto",
  general:  "general-v1",
  thesis:   "academic-v1",
  code:     "code-v1",
  calendar: "calendar-v1",
};

const BASE = "http://localhost:7842";

export async function uploadFiles(files: File[]): Promise<FileAttachment[]> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const res = await fetch(`${BASE}/api/files/upload`, {
    method: "POST",
    headers: { ..._authHeaders() }, // Do NOT set Content-Type; browser will set boundary
    body: formData,
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new ApiError(res.status, errorText || "File upload failed");
  }

  return res.json() as Promise<FileAttachment[]>;
}


function _authHeaders(): Record<string, string> {
  const key = import.meta.env.VITE_CEREBRO_KEY as string | undefined;
  return key ? { "X-Cerebro-Key": key } : {};
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ..._authHeaders() },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export async function queryAgent(
  req: QueryRequest,
  signal?: AbortSignal
): Promise<QueryResponse> {
  return request<QueryResponse>("/api/query", {
    method: "POST",
    body: JSON.stringify(req),
    signal,
  });
}

export async function queryAgentStream(
  req: QueryRequest,
  onToken: (token: string) => void,
  signal?: AbortSignal,
  onConversationId?: (id: string) => void,
  onModelSwap?: (event: ModelSwapEvent) => void,
  onContextSources?: (event: ContextSourcesEvent) => void,
): Promise<ResponseMetadata | null> {
  const res = await fetch(`${BASE}/api/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ..._authHeaders() },
    body: JSON.stringify(req),
    signal,
  });
  if (!res.ok || !res.body) throw new ApiError(res.status, res.statusText);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let metadata: ResponseMetadata | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6).trim();
      if (payload === "[DONE]") return metadata;
      let streamError: string | null = null;
      try {
        const parsed = JSON.parse(payload) as Record<string, unknown>;
        if (typeof parsed.token === "string") {
          onToken(parsed.token);
        } else if (parsed.type === "context_sources") {
          onContextSources?.(parsed as unknown as ContextSourcesEvent);
        } else if (parsed.metadata) {
          metadata = parsed.metadata as ResponseMetadata;
          if (typeof parsed.conversation_id === "string") {
            onConversationId?.(parsed.conversation_id);
          }
        } else if (parsed.model_swap) {
          onModelSwap?.(parsed.model_swap as ModelSwapEvent);
        } else if (typeof parsed.error === "string") {
          streamError = parsed.error;
        }
      } catch {
        // ignore malformed SSE lines
      }
      if (streamError) throw new Error(streamError);
    }
  }
  return metadata;
}

export async function getFleetStatus(): Promise<FleetStatus> {
  return request<FleetStatus>("/api/fleet/status");
}

export async function getFleetModels(): Promise<FleetModelsResponse> {
  return request<FleetModelsResponse>("/api/fleet/models");
}

export async function setFleetMode(
  mode: "auto" | "pinned",
  pinned_model_id?: string
): Promise<void> {
  return request<void>("/api/fleet/config", {
    method: "PATCH",
    body: JSON.stringify({ mode, pinned_model_id }),
  });
}

export async function getStatus(): Promise<StatusResponse> {
  return request<StatusResponse>("/api/status");
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health", { signal });
}

export async function startIndex(paths: string[]): Promise<IndexResponse> {
  return request<IndexResponse>("/api/index", {
    method: "POST",
    body: JSON.stringify({ paths }),
  });
}

export async function getIndexStatus(jobId: string): Promise<IndexStatusResponse> {
  return request<IndexStatusResponse>(`/api/index/status?job_id=${jobId}`);
}

export async function getConfig(): Promise<AppConfig> {
  return request<AppConfig>("/api/config");
}

export async function updateConfig(
  patch: Partial<AppConfig>
): Promise<AppConfig> {
  return request<AppConfig>("/api/config", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function switchInferenceBackend(
  backend: "llamacpp" | "claude" | "mlx"
): Promise<AppConfig> {
  return updateConfig({ inference_backend: backend });
}

export async function getModels(): Promise<ModelsResponse> {
  return request<ModelsResponse>("/api/models");
}

export async function getLlamaCppModels(): Promise<LlamaCppModelsResponse> {
  return request<LlamaCppModelsResponse>("/api/llama-cpp/models");
}

export async function listConversations(): Promise<ConversationSummary[]> {
  return request<ConversationSummary[]>("/api/conversations");
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  return request<ConversationDetail>(`/api/conversations/${id}`);
}

export async function listDocuments(): Promise<DocumentInfo[]> {
  return request<DocumentInfo[]>("/api/documents");
}

export async function deleteDocument(sourcePath: string): Promise<{ deleted: number; source_path: string }> {
  return request<{ deleted: number; source_path: string }>(
    `/api/documents?source_path=${encodeURIComponent(sourcePath)}`,
    { method: "DELETE" }
  );
}

export async function confirmTool(
  conversationId: string,
  decision: "approve" | "deny"
): Promise<QueryResponse> {
  return request<QueryResponse>("/api/tool-confirm", {
    method: "POST",
    body: JSON.stringify({ conversation_id: conversationId, decision }),
  });
}

export async function getWizardStatus(): Promise<WizardStatus> {
  return request<WizardStatus>("/api/wizard/status");
}

export async function wizardCheckLlamaCpp(): Promise<{
  running: boolean;
  skipped?: boolean;
  status?: string;
  reason?: string;
}> {
  return request<{
    running: boolean;
    skipped?: boolean;
    status?: string;
    reason?: string;
  }>("/api/wizard/check-llamacpp", { method: "POST" });
}

export async function wizardCheckModels(): Promise<{
  ok: boolean;
  message?: string;
  detail?: string;
  skipped?: boolean;
  status?: string;
  models?: string[];
}> {
  return request<{
    ok: boolean;
    message?: string;
    detail?: string;
    skipped?: boolean;
    status?: string;
    models?: string[];
  }>("/api/wizard/check-models", { method: "POST" });
}

export async function wizardReprobeCalendarPermission(): Promise<{
  calendar: string;
}> {
  return request<{ calendar: string }>(
    "/api/wizard/reprobe-calendar-permission",
    { method: "POST" },
  );
}

export async function wizardSetFolders(
  folders: string[]
): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>("/api/wizard/set-folders", {
    method: "POST",
    body: JSON.stringify({ folders }),
  });
}

export async function wizardComplete(): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>("/api/wizard/complete", { method: "POST" });
}

// ── Desktop Automation ────────────────────────────────────────────────

export interface ToolInfo {
  name: string;
  description: string;
  required_permission: string;
  requires_confirmation: boolean;
  scope: string;
  audit_level: string;
  enabled: boolean;
  parameters: Record<string, string>;
}

export async function listTools(): Promise<ToolInfo[]> {
  return request<ToolInfo[]>("/api/tools");
}

export async function listWorkflows(): Promise<Workflow[]> {
  return request<Workflow[]>("/api/workflows");
}

export async function getWorkflow(id: string): Promise<Workflow> {
  return request<Workflow>(`/api/workflows/${id}`);
}

export async function deleteWorkflow(id: string): Promise<void> {
  await request<void>(`/api/workflows/${id}`, { method: "DELETE" });
}

export async function runWorkflow(id: string): Promise<{ result: string }> {
  return request<{ result: string }>(`/api/workflows/${id}/run`, {
    method: "POST",
  });
}

// ── Time-Travel Debugger ───────────────────────────────────────────────

export async function listDebugRuns(
  limit = 50,
  offset = 0
): Promise<DebugRun[]> {
  return request<DebugRun[]>(
    `/api/debug/runs?limit=${limit}&offset=${offset}`
  );
}

export async function getDebugRunSteps(
  runId: string
): Promise<DebugStep[]> {
  return request<DebugStep[]>(`/api/debug/runs/${runId}/steps`);
}

export async function getDebugStepDetail(
  stepId: string
): Promise<DebugStepDetail> {
  return request<DebugStepDetail>(`/api/debug/steps/${stepId}`);
}
