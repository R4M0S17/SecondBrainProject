import type { Message } from "../../stores/chat";
import MessageFooter from "./MessageFooter";
import SourcesPanel from "./SourcesPanel";
import ToolHistoryPanel from "./ToolHistoryPanel";
import MemoryPanel from "./MemoryPanel";

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const { role, content, metadata, expandedPanel, id } = message;

  if (role === "user") {
    return (
      <div className="flex justify-end" role="article" aria-label="Your message">
        <div className="bg-[#444652] text-[#e8eaf0] px-4 py-2 rounded-full max-w-[85%] text-[14px] leading-[20px]">
          {content}
        </div>
      </div>
    );
  }

  // Assistant message
  return (
    <div className="space-y-3" role="article" aria-label="Assistant message">
      <div className="flex items-start gap-3">
        <div className="flex-1 space-y-2">
          <p className="text-[14px] leading-[20px] text-[#e5e0ed] whitespace-pre-wrap">
            {content}
          </p>
          {metadata && (
            <MessageFooter
              messageId={id}
              metadata={metadata}
              expandedPanel={expandedPanel}
            />
          )}
        </div>
      </div>

      {/* Expandable panels */}
      {metadata && expandedPanel === "sources" && (
        <SourcesPanel sources={metadata.sources_used} />
      )}
      {metadata && expandedPanel === "tools" && (
        <ToolHistoryPanel tools={metadata.tools_called} />
      )}
      {metadata && expandedPanel === "memory" && (
        <MemoryPanel memory={metadata.memory_retrieved} />
      )}
    </div>
  );
}
