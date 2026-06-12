export interface SourceRef {
  path: string;
  chunk_index: number;
  score: number;
}

export interface PendingTool {
  name: string;
  args: Record<string, unknown>;
}

export interface ToolCallRecord {
  name: string;
  args_summary: string;
  result_summary: string;
  latency_ms: number;
  approved: boolean;
}

export interface MemoryRef {
  id: string;
  summary_snippet: string;
  relevance_score: number;
}

export interface ResponseMetadata {
  sources_used: SourceRef[];
  tools_called: ToolCallRecord[];
  memory_retrieved: MemoryRef[];
  inference_latency_ms: number;
  total_latency_ms: number;
  iterations: number;
  model_used: string;
  provider_used: string;
  warnings: string[];
  pipeline_stages_ms: Record<string, number>;
  pending_tool?: PendingTool | null;
  // Fleet orchestrator extensions
  model_id?: string;
  quantization?: string;
  gpu_layers_used?: number;
  model_swap_occurred?: boolean;
  selection_rationale?: string;
}

export interface FileAttachment {
  filename: string;
  mime_type: string;
  content: string; // raw text for docs/PDFs or base64 for images
  type: string; // "pdf" | "image" | "text" | "unknown"
}

export interface QueryRequest {
  question: string;
  agent?: string;
  conversation_id?: string;
  attachments?: FileAttachment[];
}

export interface QueryResponse {
  answer: string;
  metadata: ResponseMetadata;
  conversation_id: string;
}

export interface ConversationMessage {
  role: string;
  content: string;
  timestamp: string;
  metadata?: ResponseMetadata | null;
}

export interface ConversationSummary {
  conv_id: string;
  agent_id: string;
  started_at: string;
  last_active: string;
  message_count: number;
  first_user_message: string;
}

export interface ConversationDetail {
  conv_id: string;
  agent_id: string;
  started_at: string;
  last_active: string;
  messages: ConversationMessage[];
}

export interface IndexResponse {
  status: string;
  job_id: string;
}

export interface IndexStatusResponse {
  job_id: string;
  status: "running" | "done" | "error";
  files_indexed: number;
  message: string;
}

export interface HealthResponse {
  llama_server: "up" | "restarting" | "down";
  last_restart_at: string | null;
  restart_count_session: number;
  message: string | null;
}

export interface StatusResponse {
  indexed_files: number;
  engine_ok: boolean;
  model: string;
  provider: string;
  active_agent: string;
  ram_pressure: "ok" | "warn" | "critical";
  ram_total_gb: number;
  ram_used_gb: number;
  ram_available_gb: number;
  cpu_percent: number;
  queries_total: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  tool_call_count: number;
  memory_hits: number;
  provider_fallbacks: number;
  context_window?: number;
  // Fleet orchestrator extensions
  current_model_id?: string;
  quantization?: string;
  gpu_layers_used?: number;
  ram_pressure_pct?: number;
  swap_in_progress?: boolean;
  model_swaps_session?: number;
  macos_permissions?: Record<string, string> | null;
}

export interface HardwareSnapshot {
  ram_total_gb: number;
  ram_available_gb: number;
  ram_pressure_pct: number;
  gpu_backend: "metal" | "cuda" | "none";
  gpu_vram_total_gb: number;
  gpu_vram_available_gb: number;
  unified_memory: boolean;
}

export interface FleetModelEntry {
  id: string;
  family: string;
  path: string;
  params_b: number;
  quant: string;
  ram_required_gb: number;
  vram_required_gb: number;
  gpu_layers: number;
  context_length: number;
  capabilities: string[];
  speed_tokens_per_sec: number;
  available_on_disk: boolean;
}

export interface FleetStatus {
  current_model: FleetModelEntry;
  hardware: HardwareSnapshot;
  swap_in_progress: boolean;
  swap_target_model_id: string | null;
  model_swaps_session: number;
  selection_rationale: string;
  mode: "auto" | "pinned";
}

export interface FleetModelsResponse {
  models: FleetModelEntry[];
  active_model_id: string;
}

export interface ContextSourcesEvent {
  sources: string[];
  episode_count: number;
}

export interface ModelSwapEvent {
  phase: "started" | "complete";
  from_model: string;
  to_model: string;
  reason: string;
  estimated_seconds?: number;
}

export interface WizardStatus {
  is_first_launch: boolean;
  engine_running: boolean;
  model_pulled: boolean;
  folders_configured: boolean;
  recommend_lite: boolean;
}

export interface AppConfig {
  model: string;
  watched_folders: string[];
  tool_permissions: {
    execute_python: boolean;
    write_file: boolean;
    read_file: boolean;
    search_web: boolean;
  };
  dnd_enabled: boolean;
  embedding_model: string;
  inference_backend: "llamacpp" | "claude" | "mlx";
  /** When false, MLX secondary provider is disabled (persisted for lite / 8 GB setups). */
  mlx_enabled?: boolean;
}

export interface LocalModel {
  name: string;
  size_gb: number;
  provider: "llamacpp" | "mlx" | "claude";
}

export interface ModelsResponse {
  models: LocalModel[];
  active_model: string | null;
}

export interface LlamaCppModel {
  name: string;
  size_gb: number;
  provider: "llama_cpp";
}

export interface LlamaCppModelsResponse {
  models: LlamaCppModel[];
  active_model: string | null;
}

export interface DocumentInfo {
  source_path: string;
  file_modified: number;
  filename: string;
}

export type AgentId = "auto" | "general" | "thesis" | "code" | "calendar";

export interface Agent {
  id: AgentId;
  label: string;
  description: string;
}

export const AGENTS: Agent[] = [
  {
    id: "auto",
    label: "Auto (router)",
    description: "Picks the best agent for each question",
  },
  { id: "general", label: "General", description: "All-purpose assistant" },
  { id: "thesis", label: "Thesis", description: "Academic writing & research" },
  { id: "code", label: "Code", description: "Programming & debugging" },
  { id: "calendar", label: "Calendar", description: "Schedule & tasks" },
];

// ── Time-Travel Debugger types ──────────────────────────────────────────

export interface DebugRun {
  id: string;
  agent_id: string;
  query: string;
  conversation_id: string | null;
  created_at: number;
  duration_ms: number | null;
  success: boolean;
}

export interface DebugStep {
  id: string;
  run_id: string;
  step_number: number;
  node_name: string;
  input_preview: string | null;
  output_preview: string | null;
  tool_name: string | null;
  tool_args_json: string | null;
  tool_result_preview: string | null;
  needs_confirmation: boolean;
  timestamp: number;
}

export interface DebugStepDetail extends DebugStep {
  tokens: { token_order: number; token_text: string; is_final: number }[];
}

// ── Desktop Automation types ──────────────────────────────────────────

export interface Workflow {
  id: string;
  name: string;
  description: string;
  applescript: string;
  parameters: { name: string; type: string; description: string }[];
  tags: string[];
  created_at: number;
  updated_at: number;
  run_count: number;
  last_run: number | null;
}

// ── Claude models ───────────────────────────────────────────────────────

export interface ClaudeModel {
  id: string;
  label: string;
  context_k: number;
  note: string;
}

export const CLAUDE_MODELS: ClaudeModel[] = [
  { id: "claude-opus-4-7",           label: "Claude Opus 4.7",   context_k: 200, note: "Most capable" },
  { id: "claude-sonnet-4-6",         label: "Claude Sonnet 4.6", context_k: 200, note: "Best balance (default)" },
  { id: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5",  context_k: 200, note: "Fastest · lowest cost" },
];
