import { ApiError } from "./errors";
import { isTauriRuntime } from "../lib/tauri";
import type { TranscribeResponse, TranscribeHealthResponse } from "./types";

let _cerebroKey: string | null = null;

/** Cross-origin fetch that works from both Tauri webview and browser dev mode. */
async function crossFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  if (isTauriRuntime()) {
    const { fetch } = await import("@tauri-apps/plugin-http");
    return fetch(input, init);
  }
  return window.fetch(input, init);
}

async function ipcRequest<T>(method: string, path: string, body?: string): Promise<T> {
  const { invoke } = await import("@tauri-apps/api/core");
  const raw = await invoke<string>("proxy_api_request", {
    method,
    path,
    body: body ?? null,
    apiKey: _cerebroKey,
  });
  return JSON.parse(raw) as T;
}

export function setApiKey(key: string | null): void {
  _cerebroKey = key;
}

export function getApiKey(): string | null {
  return _cerebroKey;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const method = (options?.method as string) || "GET";
  const body = options?.body as string | undefined;
  try {
    if (isTauriRuntime()) {
      const { invoke } = await import("@tauri-apps/api/core");
      const raw = await invoke<string>("proxy_api_request", {
        method,
        path,
        body: body ?? null,
        apiKey: _cerebroKey,
      });
      return JSON.parse(raw) as T;
    }
    const res = await crossFetch(`http://127.0.0.1:7842${path}`, options);
    if (!res.ok) {
      let detail: string;
      try {
        const json = (await res.json()) as { detail?: unknown };
        detail = typeof json.detail === "string" ? json.detail : JSON.stringify(json.detail ?? res.statusText);
      } catch {
        detail = await res.text();
      }
      throw new ApiError(res.status, detail);
    }
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    const msg = typeof e === "string" ? e : e instanceof Error ? e.message : String(e);
    const statusMatch = msg.match(/\b(GET|POST|PATCH|DELETE)\s+(\d{3}):\s*(.+)/s);
    if (statusMatch) {
      const status = Number(statusMatch[2]);
      let detail = statusMatch[3].trim();
      try {
        const parsed = JSON.parse(detail) as { detail?: unknown };
        if (typeof parsed.detail === "string") detail = parsed.detail;
        else if (parsed.detail != null) detail = JSON.stringify(parsed.detail);
      } catch {
        // keep raw body
      }
      throw new ApiError(status, detail);
    }
    throw e instanceof Error ? e : new Error(msg);
  }
}

// ── Type imports (keep in sync with types.ts) ──────────────────────────

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
  EngineStatusResponse,
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
  WorkflowRun,
  WorkflowRunResponse,
  WorkflowRecipe,
  WorkflowExport,
  WorkflowStep,
  RecordingStatus,
  SyncSource,
  SyncResult,
  SyncTriggerPayload,
  MemoryRecallResponse,
  MemoryEpisodesResponse,
  MemorySessionContext,
  MemoryEpisode,
  FolderAnalyzeRequest,
  FolderAnalyzeResponse,
  DocumentSearchRequest,
  DocumentSearchResponse,
} from "./types";

export const AGENT_ID_MAP: Record<AgentId, string> = {
  auto:     "auto",
  general:  "general-v1",
  thesis:   "academic-v1",
  code:     "code-v1",
  calendar: "calendar-v1",
};

// ── Non-streaming helpers fall back to fetch for now ────────────────────
// TODO: proxy these through IPC as well for full webview isolation.

function _authHeaders(): Record<string, string> {
  return _cerebroKey ? { "X-Cerebro-Key": _cerebroKey } : {};
}

export async function writeQuickNote(content: string, title?: string): Promise<{ status: string; path: string }> {
  return request<{ status: string; path: string }>("/api/quick-note", {
    method: "POST",
    body: JSON.stringify({ content, title }),
  });
}

export async function analyzeFolder(body: FolderAnalyzeRequest): Promise<FolderAnalyzeResponse> {
  return request<FolderAnalyzeResponse>("/api/folder/analyze", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function uploadFiles(files: File[]): Promise<FileAttachment[]> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const res = await crossFetch("http://localhost:7842/api/files/upload", {
    method: "POST",
    headers: { ..._authHeaders() },
    body: formData,
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new ApiError(res.status, errorText || "File upload failed");
  }
  return res.json() as Promise<FileAttachment[]>;
}

export async function getHealth(_signal?: AbortSignal): Promise<HealthResponse> {
  return ipcRequest<HealthResponse>("GET", "/api/health");
}

export async function getStatus(): Promise<StatusResponse> {
  return ipcRequest<StatusResponse>("GET", "/api/status");
}

export async function getEngineActivity(): Promise<{ engine_state: "active" | "suspended" | "unknown" }> {
  return ipcRequest<{ engine_state: "active" | "suspended" | "unknown" }>("GET", "/api/engine/activity");
}

export async function getEngineStatus(): Promise<EngineStatusResponse> {
  return ipcRequest<EngineStatusResponse>("GET", "/api/engine/status");
}

export async function startEngine(): Promise<EngineStatusResponse> {
  return ipcRequest<EngineStatusResponse>("POST", "/api/engine/start");
}

export async function stopEngine(): Promise<EngineStatusResponse> {
  return ipcRequest<EngineStatusResponse>("POST", "/api/engine/stop");
}

export async function queryAgent(req: QueryRequest, _signal?: AbortSignal): Promise<QueryResponse> {
  return request<QueryResponse>("/api/query", {
    method: "POST",
    body: JSON.stringify(req),
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
  const res = await crossFetch("http://localhost:7842/api/query/stream", {
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

// ── Everything below uses the proxied `request` ────────────────────────

export async function startIndex(paths: string[]): Promise<IndexResponse> {
  return request<IndexResponse>("/api/index", {
    method: "POST",
    body: JSON.stringify({ paths }),
  });
}

export async function getIndexStatus(jobId: string): Promise<IndexStatusResponse> {
  return request<IndexStatusResponse>(`/api/index/status?job_id=${jobId}`);
}

export async function getFleetStatus(): Promise<FleetStatus> {
  return request<FleetStatus>("/api/fleet/status");
}

export async function getFleetModels(): Promise<FleetModelsResponse> {
  return request<FleetModelsResponse>("/api/fleet/models");
}

export async function setFleetMode(mode: "auto" | "pinned", pinned_model_id?: string): Promise<void> {
  return request<void>("/api/fleet/config", {
    method: "PATCH",
    body: JSON.stringify({ mode, pinned_model_id }),
  });
}

export async function getConfig(): Promise<AppConfig> {
  return request<AppConfig>("/api/config");
}

export async function updateConfig(patch: Partial<AppConfig>): Promise<AppConfig> {
  return request<AppConfig>("/api/config", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function switchInferenceBackend(backend: "llamacpp" | "claude" | "mlx"): Promise<AppConfig> {
  return updateConfig({ inference_backend: backend });
}

export async function updateClaudeApiKey(key: string): Promise<AppConfig> {
  return updateConfig({ anthropic_api_key: key } as Partial<AppConfig>);
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

export async function deleteConversation(id: string): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`/api/conversations/${id}`, { method: "DELETE" });
}

export async function searchConversations(q: string): Promise<ConversationSummary[]> {
  const params = new URLSearchParams({ q });
  return request<ConversationSummary[]>(`/api/conversations/search?${params}`);
}

export async function patchConversation(id: string, patch: { pinned?: boolean }): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/conversations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function batchDeleteConversations(ids: string[]): Promise<{ deleted: number }> {
  return request<{ deleted: number }>("/api/conversations/batch-delete", {
    method: "POST",
    body: JSON.stringify({ ids }),
  });
}

export async function batchPinConversations(ids: string[], pinned: boolean): Promise<{ updated: number }> {
  return request<{ updated: number }>("/api/conversations/batch-pin", {
    method: "POST",
    body: JSON.stringify({ ids, pinned }),
  });
}

export async function listDocuments(): Promise<DocumentInfo[]> {
  return request<DocumentInfo[]>("/api/documents");
}

export async function searchDocuments(
  req: DocumentSearchRequest,
): Promise<DocumentSearchResponse> {
  return request<DocumentSearchResponse>("/api/documents/search", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function deleteDocument(sourcePath: string): Promise<{ deleted: number; source_path: string }> {
  return request<{ deleted: number; source_path: string }>(
    `/api/documents?source_path=${encodeURIComponent(sourcePath)}`,
    { method: "DELETE" }
  );
}

export async function listMemoryEpisodes(
  agentId?: string,
  limit = 100,
): Promise<MemoryEpisodesResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (agentId) params.set("agent_id", agentId);
  return request<MemoryEpisodesResponse>(`/api/memory/episodes?${params}`);
}

export async function getMemorySession(agentId?: string): Promise<MemorySessionContext> {
  const q = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : "";
  return request<MemorySessionContext>(`/api/memory/session${q}`);
}

export async function createMemoryEpisode(
  content: string,
  tags?: string[],
  agentId?: string,
): Promise<MemoryEpisode> {
  return request<MemoryEpisode>("/api/memory/episodes", {
    method: "POST",
    body: JSON.stringify({ content, tags, agent_id: agentId }),
  });
}

export async function deleteMemoryEpisode(
  episodeId: string,
  agentId?: string,
): Promise<{ deleted: boolean; id: string }> {
  const q = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : "";
  return request<{ deleted: boolean; id: string }>(
    `/api/memory/episodes/${encodeURIComponent(episodeId)}${q}`,
    { method: "DELETE" },
  );
}

export async function patchMemoryEpisode(
  episodeId: string,
  patch: { content?: string; tags?: string[]; pinned?: boolean; agent_id?: string },
): Promise<MemoryEpisode> {
  return request<MemoryEpisode>(`/api/memory/episodes/${encodeURIComponent(episodeId)}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function recallMemory(
  query: string,
  agentId?: string,
): Promise<MemoryRecallResponse> {
  return request<MemoryRecallResponse>("/api/memory/recall", {
    method: "POST",
    body: JSON.stringify({ query, agent_id: agentId }),
  });
}

export async function confirmTool(conversationId: string, decision: "approve" | "deny"): Promise<QueryResponse> {
  return request<QueryResponse>("/api/tool-confirm", {
    method: "POST",
    body: JSON.stringify({ conversation_id: conversationId, decision }),
  });
}

export async function getWizardStatus(): Promise<WizardStatus> {
  return request<WizardStatus>("/api/wizard/status");
}

export async function wizardCheckLlamaCpp(): Promise<{ running: boolean; skipped?: boolean; status?: string; reason?: string }> {
  return request<{ running: boolean; skipped?: boolean; status?: string; reason?: string }>(
    "/api/wizard/check-llamacpp", { method: "POST" }
  );
}

export async function wizardCheckModels(): Promise<{ ok: boolean; message?: string; detail?: string; skipped?: boolean; status?: string; models?: string[] }> {
  return request<{ ok: boolean; message?: string; detail?: string; skipped?: boolean; status?: string; models?: string[] }>(
    "/api/wizard/check-models", { method: "POST" }
  );
}

export async function wizardReprobeCalendarPermission(): Promise<{ calendar: string }> {
  return request<{ calendar: string }>("/api/wizard/reprobe-calendar-permission", { method: "POST" });
}

export async function wizardSetFolders(folders: string[]): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>("/api/wizard/set-folders", {
    method: "POST",
    body: JSON.stringify({ folders }),
  });
}

export async function wizardComplete(): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>("/api/wizard/complete", { method: "POST" });
}

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

export async function runWorkflow(
  id: string,
  params?: Record<string, string>,
  options?: { dryRun?: boolean },
): Promise<WorkflowRunResponse> {
  return request<WorkflowRunResponse>(`/api/workflows/${id}/run`, {
    method: "POST",
    body: JSON.stringify({ params: params ?? {}, dry_run: options?.dryRun ?? false }),
  });
}

export async function listWorkflowRuns(id: string, limit = 20): Promise<WorkflowRun[]> {
  return request<WorkflowRun[]>(`/api/workflows/${id}/runs?limit=${limit}`);
}

export async function listRecipeTemplates(): Promise<WorkflowRecipe[]> {
  return request<WorkflowRecipe[]>("/api/workflows/recipes/templates");
}

export async function installRecipe(
  templateId: string,
  name?: string,
): Promise<Workflow> {
  return request<Workflow>("/api/workflows/recipes", {
    method: "POST",
    body: JSON.stringify({ template_id: templateId, name }),
  });
}

export async function startWorkflowRecording(): Promise<{ status: string; started_at: number }> {
  return request<{ status: string; started_at: number }>("/api/workflows/record/start", {
    method: "POST",
  });
}

export async function getWorkflowRecordingStatus(): Promise<RecordingStatus> {
  return request<RecordingStatus>("/api/workflows/record/status");
}

export async function stopWorkflowRecording(name?: string): Promise<Workflow> {
  return request<Workflow>("/api/workflows/record/stop", {
    method: "POST",
    body: name ? JSON.stringify({ name }) : undefined,
  });
}

export async function cancelWorkflowRecording(): Promise<{ status: string }> {
  return request<{ status: string }>("/api/workflows/record/cancel", { method: "POST" });
}

export async function updateWorkflow(
  id: string,
  patch: {
    name?: string;
    description?: string;
    tags?: string[];
    steps?: WorkflowStep[];
    applescript?: string;
  },
): Promise<Workflow> {
  return request<Workflow>(`/api/workflows/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function exportWorkflow(id: string): Promise<WorkflowExport> {
  return request<WorkflowExport>(`/api/workflows/${id}/export`);
}

export async function importWorkflow(exportData: WorkflowExport): Promise<Workflow> {
  return request<Workflow>("/api/workflows/import", {
    method: "POST",
    body: JSON.stringify({ export: exportData }),
  });
}

export async function saveRecipeFromConversation(
  conversationId: string,
  turnIndex: number,
  name?: string,
): Promise<Workflow> {
  return request<Workflow>("/api/workflows/from-conversation", {
    method: "POST",
    body: JSON.stringify({ conversation_id: conversationId, turn_index: turnIndex, name }),
  });
}

export async function listDebugRuns(limit = 50, offset = 0): Promise<DebugRun[]> {
  return request<DebugRun[]>(`/api/debug/runs?limit=${limit}&offset=${offset}`);
}

export async function getDebugRunSteps(runId: string): Promise<DebugStep[]> {
  return request<DebugStep[]>(`/api/debug/runs/${runId}/steps`);
}

export async function getDebugStepDetail(stepId: string): Promise<DebugStepDetail> {
  return request<DebugStepDetail>(`/api/debug/steps/${stepId}`);
}

export async function listSyncSources(): Promise<SyncSource[]> {
  return request<SyncSource[]>("/api/knowledge-sync/sources");
}

export async function addSyncSource(source: SyncSource): Promise<{ status: string; id: string }> {
  return request<{ status: string; id: string }>("/api/knowledge-sync/sources", {
    method: "POST",
    body: JSON.stringify(source),
  });
}

export async function removeSyncSource(sourceId: string): Promise<{ status: string }> {
  return request<{ status: string }>(`/api/knowledge-sync/sources/${encodeURIComponent(sourceId)}`, { method: "DELETE" });
}

export async function triggerSync(payload: SyncTriggerPayload): Promise<{ status: string }> {
  return request<{ status: string }>("/api/knowledge-sync/sync", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function syncOneSource(sourceId: string): Promise<SyncResult> {
  return request<SyncResult>(`/api/knowledge-sync/sync/${encodeURIComponent(sourceId)}`, { method: "POST" });
}

export async function getSyncSourceState(sourceId: string): Promise<{ source_id: string; status: string; last_sync_at: number; last_error: string; items_indexed: number }> {
  return request<{ source_id: string; status: string; last_sync_at: number; last_error: string; items_indexed: number }>(
    `/api/knowledge-sync/sources/${encodeURIComponent(sourceId)}/state`
  );
}

export async function triggerSyncStream(
  payload: SyncTriggerPayload,
  onProgress: (event: { stage: string; [key: string]: unknown }) => void,
  onComplete: (result: { source_id: string; indexed: number; errors: string[] }) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await crossFetch("http://localhost:7842/api/knowledge-sync/sync/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", ..._authHeaders() },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok || !res.body) throw new ApiError(res.status, res.statusText);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const block of parts) {
      const lines = block.split("\n");
      let eventType = "message";
      let dataStr = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) eventType = line.slice(7).trim();
        else if (line.startsWith("data: ")) dataStr = line.slice(6).trim();
      }
      if (!dataStr) continue;
      if (eventType === "done") return;
      try {
        const data = JSON.parse(dataStr) as Record<string, unknown>;
        if (eventType === "progress") {
          onProgress(data as { stage: string; [key: string]: unknown });
        } else if (eventType === "complete") {
          onComplete(data as { source_id: string; indexed: number; errors: string[] });
        }
      } catch {
        // ignore malformed data
      }
    }
  }
}

export async function exportSyncSources(): Promise<{ version: number; exported_at: string; sources: { id: string; source_type: string; uri: string; label: string; interval_minutes: number; tags: string[]; schedule_cron: string }[] }> {
  return request("/api/knowledge-sync/export");
}

export async function importSyncSources(payload: { version: number; sources: { id: string; source_type: string; uri: string; label: string; interval_minutes: number; tags: string[]; schedule_cron: string }[] }): Promise<{ status: string; added: number; errors: string[] }> {
  return request("/api/knowledge-sync/import", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function transcribeAudio(
  audioBlob: Blob,
  language = "auto",
): Promise<TranscribeResponse> {
  const formData = new FormData();
  formData.append("file", audioBlob, "audio.wav");
  formData.append("language", language);
  const res = await crossFetch("http://127.0.0.1:7842/api/transcribe", {
    method: "POST",
    headers: { ..._authHeaders() },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, err.detail ?? "Transcription error");
  }
  return res.json() as Promise<TranscribeResponse>;
}

export async function getTranscribeHealth(): Promise<TranscribeHealthResponse> {
  return request<TranscribeHealthResponse>("/api/transcribe/health");
}

export async function startTranscribe(): Promise<{ status: string }> {
  return request<{ status: string }>("/api/transcribe/start", { method: "POST" });
}

export async function stopTranscribe(): Promise<{ status: string }> {
  return request<{ status: string }>("/api/transcribe/stop", { method: "POST" });
}

export async function getEmbeddingCacheStats(): Promise<import("./types").EmbeddingCacheStats> {
  return request<import("./types").EmbeddingCacheStats>("/api/cache/embedding-stats");
}

export interface ModelDownloadResponse {
  ok: boolean;
  detail: string;
  path?: string;
  size_gb?: number;
}

export async function downloadModel(url: string, filename: string): Promise<ModelDownloadResponse> {
  return request<ModelDownloadResponse>("/api/models/download", {
    method: "POST",
    body: JSON.stringify({ url, filename }),
  });
}

export const AVAILABLE_MODELS: { filename: string; url: string; repo: string; sizeGb: string; note: string }[] = [
  { filename: "Qwen3.5-2B-UD-Q4_K_XL.gguf", url: "https://huggingface.co/Qwen/Qwen3.5-2B-UD-Q4_K_XL-GGUF/resolve/main/Qwen3.5-2B-UD-Q4_K_XL.gguf", repo: "Qwen/Qwen3.5-2B-UD-Q4_K_XL-GGUF", sizeGb: "1.2 GB", note: "Multimodal · 262K ctx" },
  { filename: "Qwen_Qwen3.5-2B-Q4_K_M.gguf", url: "https://huggingface.co/Qwen/Qwen3.5-2B-Q4_K_M-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf", repo: "Qwen/Qwen3.5-2B-Q4_K_M-GGUF", sizeGb: "1.3 GB", note: "Text-only · 262K ctx" },
  { filename: "Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf", url: "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M-GGUF/resolve/main/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf", repo: "Qwen/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M-GGUF", sizeGb: "0.9 GB", note: "Code-specialized" },
  { filename: "Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf", url: "https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507-Q4_K_M-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf", repo: "Qwen/Qwen3-4B-Instruct-2507-Q4_K_M-GGUF", sizeGb: "2.3 GB", note: "Strong reasoning" },
  { filename: "Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf", url: "https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-Q4_K_M-GGUF/resolve/main/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf", repo: "Qwen/Qwen2.5-Coder-3B-Instruct-Q4_K_M-GGUF", sizeGb: "1.8 GB", note: "Larger code model" },
  { filename: "llama-3.2-3b-instruct-q4_k_m.gguf", url: "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf", repo: "bartowski/Llama-3.2-3B-Instruct-GGUF", sizeGb: "1.9 GB", note: "Meta · efficient" },
];
