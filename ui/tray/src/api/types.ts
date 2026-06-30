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
  timestamp?: string;
}

export interface MemoryRef {
  id: string;
  summary_snippet: string;
  relevance_score: number;
}

/** Long-term agent memory episode (LanceDB agent_memory). Frontend-only mock until API ships. */
export interface MemoryEpisode {
  id: string;
  content: string;
  tags: string[];
  created_at: number;
  confidence: number;
  source: "episode" | "consolidation" | "archived" | "manual";
  pinned: boolean;
  agent_id: string;
}

export interface MemorySessionContext {
  session_summary: string;
  working_memory: Record<string, string>;
  last_consolidation_at: number | null;
  messages_in_short_term: number;
}

export interface MemoryBrowserStats {
  episodes_stored: number;
  recall_hits_session: number;
  queries_with_recall: number;
  context_memory_pct: number;
}

export interface MemoryRecallResult {
  episode: MemoryEpisode;
  relevance_score: number;
}

export interface MemoryEpisodesResponse {
  episodes: MemoryEpisode[];
  stats: MemoryBrowserStats;
}

export interface MemoryRecallResponse {
  results: MemoryRecallResult[];
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
  pinned?: boolean;
}

export interface ConversationDetail {
  conv_id: string;
  agent_id: string;
  started_at: string;
  last_active: string;
  messages: ConversationMessage[];
  pinned?: boolean;
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

export interface EngineStatusResponse {
  desired: "on" | "off";
  running: boolean;
  model: string;
  llama_server: "up" | "restarting" | "down";
  embed_running: boolean;
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
  whisper?: TranscribeHealthResponse | null;
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
  focus_mode: boolean;
  embedding_model: string;
  inference_backend: "llamacpp" | "claude" | "mlx";
  /** When false, MLX secondary provider is disabled (persisted for lite / 8 GB setups). */
  mlx_enabled?: boolean;
  /** Whether an ANTHROPIC_API_KEY has been configured. */
  claude_has_key?: boolean;
  /** API keys (stored in backend config, extra="allow") */
  anthropic_api_key?: string;
  tavily_api_key?: string;
  cerebro_api_key?: string;
  /** Inference profile: 'normal' for 2B model, 'low-power' for 0.5B model. */
  profile?: "normal" | "low-power";
  /** False while Nano v2 is in development — Low Power toggle disabled in UI. */
  low_power_available?: boolean;
  /** UI language/locale: 'en' or 'es'. */
  locale?: string;
  /** Inference parameters */
  temperature?: number;
  top_p?: number;
  top_k?: number;
  repeat_penalty?: number;
  context_length?: number;
  llamacpp_url?: string;
  embed_url?: string;
  /** Memory & RAG parameters */
  short_term_max_messages?: number;
  context_budget_pct?: number;
  consolidation_target_pct?: number;
  session_resume_max_turns?: number;
  rag_top_k?: number;
  semantic_compression?: boolean;
  embedding_cache_ttl_days?: number;
  embedding_cache_max_size?: number;
  embeddings_backend?: string;
  /** Web search parameters */
  web_backend?: string;
  web_max_results?: number;
  web_max_chars?: number;
  web_timeout?: number;
  /** Fleet & RAM parameters */
  ram_primary_gb?: number;
  ram_fallback_gb?: number;
  ram_min_available_gb?: number;
  swap_timeout?: number;
  llamacpp_simple?: boolean;
  /** Verbose logging toggle */
  log_verbose?: boolean;
  /** Knowledge sync configuration. */
  knowledge_sync?: {
    enabled: boolean;
    sources?: SyncSource[];
    interest_tags?: string[];
    max_items_per_sync?: number;
  };
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

export interface DocumentSearchRequest {
  query: string;
  mode: "chunks" | "answer";
  top_k?: number;
  source_prefix?: string | null;
}

export interface DocumentChunkHit {
  id: string;
  source_path: string;
  filename: string;
  chunk_index: number;
  content: string;
  score: number;
  snippet: string;
}

export interface DocumentSearchResponse {
  query: string;
  mode: string;
  hits: DocumentChunkHit[];
  answer: string | null;
  sources: string[];
  latency_ms: number;
  warnings: string[];
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
    label: "Auto",
    description: "Picks the best agent for each question",
  },
  { id: "general", label: "General", description: "All-purpose assistant" },
  { id: "thesis", label: "Academic", description: "Academic writing & research" },
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

export interface WorkflowStep {
  order: number;
  app?: string;
  action: string;
  detail?: string;
}

export interface WorkflowParameter {
  name: string;
  type: string;
  description: string;
  default?: string;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  workflow_type: "desktop" | "recipe";
  applescript: string;
  recipe_key?: string;
  parameters: WorkflowParameter[];
  steps: WorkflowStep[];
  tags: string[];
  created_at: number;
  updated_at: number;
  run_count: number;
  last_run: number | null;
}

export interface WorkflowRun {
  id: string;
  workflow_id: string;
  started_at: number;
  finished_at: number | null;
  success: boolean;
  output: string | null;
  error: string | null;
  params: Record<string, string>;
}

export interface RecordingPreviewEvent {
  timestamp: number;
  app: string;
  action: string;
  detail: string;
}

export interface RecordingStatus {
  recording: boolean;
  event_count: number;
  apps: string[];
  duration_sec: number;
  started_at: number | null;
  preview: RecordingPreviewEvent[];
}

export interface WorkflowRecipe {
  id: string;
  recipe_key: string;
  name: string;
  description: string;
  parameters: WorkflowParameter[];
  steps: WorkflowStep[];
  tags?: string[];
}

export interface WorkflowRunResponse {
  result: string;
  success: boolean;
  run_id?: string;
  error?: string | null;
  dry_run?: boolean;
}

export interface WorkflowExport {
  version: number;
  name: string;
  description: string;
  workflow_type: "desktop" | "recipe";
  applescript: string;
  recipe_key?: string | null;
  parameters: WorkflowParameter[];
  steps: WorkflowStep[];
  tags: string[];
}

// ── Claude models ───────────────────────────────────────────────────────

export interface ClaudeModel {
  id: string;
  label: string;
  context_k: number;
  note: string;
}

// ── Knowledge Sync types ──────────────────────────────────────────────

export type SyncSourceType = "rss" | "github" | "web" | "arxiv" | "youtube" | "pubmed";
export type SyncStatusType = "idle" | "syncing" | "error";

export interface SyncSource {
  id: string;
  source_type: SyncSourceType;
  uri: string;
  label: string;
  enabled: boolean;
  interval_minutes: number;
  max_items_per_sync: number;
  filter_min_relevance: number;
  tags: string[];
  schedule_cron: string;
  status: SyncStatusType;
  last_sync_at: number | null;
  last_error: string;
  items_indexed: number;
}

export interface SyncResult {
  source_id: string;
  fetched: number;
  filtered_out: number;
  indexed: number;
  errors: string[];
  duration_ms: number;
}

export interface SyncTriggerPayload {
  force?: boolean;
  source_id?: string;
}

export interface SyncSourceFormData {
  id: string;
  source_type: SyncSourceType;
  uri: string;
  label: string;
  interval_minutes: number;
  tags: string[];
  schedule_cron: string;
}

export interface SyncProgressEvent {
  stage: string;
  source: string;
  [key: string]: unknown;
}

export interface SyncExportPayload {
  version: number;
  exported_at: string;
  sources: {
    id: string;
    source_type: string;
    uri: string;
    label: string;
    interval_minutes: number;
    tags: string[];
    schedule_cron: string;
  }[];
}

export interface SyncImportResponse {
  status: string;
  added: number;
  errors: string[];
}

export interface FolderFileEntry {
  path: string;
  size_bytes: number;
  modified: number;
}

export interface FolderAnalyzeRequest {
  path: string;
  max_depth?: number;
  include_summary?: boolean;
}

export interface FolderAnalyzeResponse {
  path: string;
  total_files: number;
  total_dirs: number;
  total_size_mb: number;
  by_extension: Record<string, number>;
  largest_files: FolderFileEntry[];
  tree_preview: string;
  indexed_count: number;
  indexed_sample: string[];
  summary: string | null;
  warnings: string[];
}

export interface TranscribeResponse {
  text: string;
  language: string;
  duration_ms: number;
}

export interface TranscribeHealthResponse {
  available: boolean;
  running: boolean;
  reachable: boolean;
  model: string | null;
  port: number;
}

export interface EmbeddingCacheStats {
  hits: number;
  misses: number;
  hit_rate_percent: number;
  size: number;
  max_size: number;
  evictions: number;
  avg_get_latency_ms: number;
  avg_put_latency_ms: number;
  ttl_seconds: number | null;
  persistence_store: string;
}

export const CLAUDE_MODELS: ClaudeModel[] = [
  { id: "claude-opus-4-7",           label: "Claude Opus 4.7",   context_k: 200, note: "Most capable" },
  { id: "claude-sonnet-4-6",         label: "Claude Sonnet 4.6", context_k: 200, note: "Best balance (default)" },
  { id: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5",  context_k: 200, note: "Fastest · lowest cost" },
];
