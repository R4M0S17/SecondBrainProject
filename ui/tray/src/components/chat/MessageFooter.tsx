import type { ResponseMetadata } from "../../api/types";
import { useChatStore } from "../../stores/chat";

interface MessageFooterProps {
  messageId: string;
  metadata: ResponseMetadata;
  expandedPanel: "sources" | "tools" | "memory" | null | undefined;
}

function ProviderDot({ provider }: { provider: string }) {
  const color =
    provider === "claude" ? "bg-[#a78bfa]" :
    provider === "mlx" ? "bg-[#38bdf8]" :
    "bg-success-green";
  return <div className={`w-[6px] h-[6px] rounded-full shrink-0 ${color}`} />;
}

function ProviderLabel({ provider }: { provider: string }) {
  const label =
    provider === "claude" ? "Claude" :
    provider === "mlx" ? "MLX" :
    "llama.cpp";
  return <span className="font-mono text-[11px] text-on-surface-variant tracking-tight">{label}</span>;
}

function LatencyText({ ms }: { ms: number }) {
  const s = ms / 1000;
  const color = s > 15 ? "text-error" : s > 8 ? "text-tertiary-fixed-dim" : "text-outline";
  return <span className={`font-mono text-[11px] tabular-nums ${color}`}>{s.toFixed(1)}s</span>;
}

export default function MessageFooter({
  messageId,
  metadata,
  expandedPanel,
}: MessageFooterProps) {
  const togglePanel = useChatStore((s) => s.toggleMessagePanel);
  const { model_used, provider_used, total_latency_ms, sources_used, tools_called, memory_retrieved } = metadata;

  return (
    <div className="flex items-center gap-3 mt-3 flex-wrap">
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1" title={`Provider: ${provider_used}`}>
          <ProviderDot provider={provider_used} />
          <ProviderLabel provider={provider_used} />
        </div>
        <span className="font-mono text-[11px] text-outline max-w-[200px] truncate" title={model_used}>
          {model_used}
        </span>
        <LatencyText ms={total_latency_ms} />
      </div>

      {metadata.model_id && (
        <span
          className="flex items-center gap-1 font-mono text-[11px] text-outline"
          title={metadata.selection_rationale}
        >
          {metadata.model_swap_occurred && (
            <svg className="w-3 h-3 text-[#f59e0b] shrink-0" viewBox="0 0 24 24" fill="currentColor">
              <path d="M7 16V4m0 0L3 8m4-4l4 4M17 8v12m0 0l4-4m-4 4l-4-4" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" fill="none" />
            </svg>
          )}
          {metadata.model_id}{metadata.quantization ? ` · ${metadata.quantization}` : ""}
        </span>
      )}

      <div className="flex gap-1 ml-auto">
        {sources_used.length > 0 && (
          <button
            onClick={() => togglePanel(messageId, "sources")}
            className={`text-[10px] font-bold tracking-[0.05em] uppercase px-2 py-[2px] border rounded-sm transition-colors ${
              expandedPanel === "sources"
                ? "bg-surface-container border-primary-container text-primary-container"
                : "bg-surface-container border-outline-variant text-on-surface-variant hover:border-outline"
            }`}
          >
            {sources_used.length} SOURCES
          </button>
        )}
        {tools_called.length > 0 && (
          <button
            onClick={() => togglePanel(messageId, "tools")}
            className={`text-[10px] font-bold tracking-[0.05em] uppercase px-2 py-[2px] border rounded-sm transition-colors ${
              expandedPanel === "tools"
                ? "bg-surface-container border-primary-container text-primary-container"
                : "bg-surface-container border-outline-variant text-on-surface-variant hover:border-outline"
            }`}
          >
            {tools_called.length} TOOL
          </button>
        )}
        {memory_retrieved.length > 0 && (
          <button
            onClick={() => togglePanel(messageId, "memory")}
            className={`text-[10px] font-bold tracking-[0.05em] uppercase px-2 py-[2px] border rounded-sm transition-colors ${
              expandedPanel === "memory"
                ? "bg-surface-container border-primary-container text-primary-container"
                : "bg-surface-container border-outline-variant text-on-surface-variant hover:border-outline"
            }`}
          >
            {memory_retrieved.length} MEMORY
          </button>
        )}
      </div>
    </div>
  );
}
