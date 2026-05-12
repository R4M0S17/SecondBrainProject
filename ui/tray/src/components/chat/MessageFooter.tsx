import type { ResponseMetadata } from "../../api/types";
import { useChatStore } from "../../stores/chat";

interface MessageFooterProps {
  messageId: string;
  metadata: ResponseMetadata;
  expandedPanel: "sources" | "tools" | "memory" | null | undefined;
}

export default function MessageFooter({
  messageId,
  metadata,
  expandedPanel,
}: MessageFooterProps) {
  const togglePanel = useChatStore((s) => s.toggleMessagePanel);
  const { model_used, total_latency_ms, sources_used, tools_called, memory_retrieved } = metadata;

  return (
    <div className="flex items-center gap-2 mt-3">
      <span className="font-mono text-[12px] text-[#c9c4d7] opacity-60">
        {model_used} · {(total_latency_ms / 1000).toFixed(1)}s
      </span>
      {metadata.model_id && (
        <span
          className="flex items-center gap-1 font-mono text-[12px] text-[#474554]"
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
      <div className="flex gap-1">
        {sources_used.length > 0 && (
          <button
            onClick={() => togglePanel(messageId, "sources")}
            className={`text-[10px] font-bold tracking-[0.05em] uppercase px-2 py-[2px] border rounded-sm transition-colors ${
              expandedPanel === "sources"
                ? "bg-[#201f27] border-[#94a3b8] text-[#94a3b8]"
                : "bg-[#201f27] border-[#242736] text-[#c9c4d7] hover:border-[#928ea0]"
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
                ? "bg-[#201f27] border-[#94a3b8] text-[#94a3b8]"
                : "bg-[#201f27] border-[#242736] text-[#c9c4d7] hover:border-[#928ea0]"
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
                ? "bg-[#201f27] border-[#94a3b8] text-[#94a3b8]"
                : "bg-[#201f27] border-[#242736] text-[#c9c4d7] hover:border-[#928ea0]"
            }`}
          >
            {memory_retrieved.length} MEMORY
          </button>
        )}
      </div>
    </div>
  );
}
