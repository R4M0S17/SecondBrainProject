import { useState, useEffect, useRef } from "react";
import type { Message } from "../../stores/chat";
import { useChatStore } from "../../stores/chat";
import MarkdownRenderer from "./MarkdownRenderer";
import MessageFooter from "./MessageFooter";
import SourcesPanel from "./SourcesPanel";
import ToolHistoryPanel from "./ToolHistoryPanel";
import MemoryPanel from "./MemoryPanel";

function useTypewriter(fullText: string, isStreaming: boolean, speed: number = 5) {
  const [displayed, setDisplayed] = useState(0);
  const fullTextRef = useRef(fullText);
  fullTextRef.current = fullText;

  useEffect(() => {
    if (!isStreaming) {
      setDisplayed(fullText.length);
      return;
    }

    // For streaming, display immediately without artificial delay
    setDisplayed(fullText.length);

    return () => {};
  }, [isStreaming, fullText]);

  return displayed;
}

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
}

export default function MessageBubble({ message, isStreaming }: MessageBubbleProps) {
  const { role, content, metadata, expandedPanel, id } = message;
  const typewriterLen = useTypewriter(content, !!isStreaming);
  const displayText = isStreaming ? content.slice(0, typewriterLen) : content;

  if (role === "user") {
    return (
      <div className="flex justify-end" role="article" aria-label="Your message">
        <div className="max-w-[70%] bg-primary-container/15 border border-primary-container/25 rounded-2xl rounded-tr-sm p-4 text-sm text-on-surface">
          {content}
        </div>
      </div>
    );
  }

  const searchingSources = useChatStore((s) => s.searchingSources);
  const searchingWeb = useChatStore((s) => s.searchingWeb);

  return (
    <div className="flex justify-start" role="article" aria-label="Assistant message">
      <div className="flex gap-4 max-w-[80%]">
        <div className="w-8 h-8 rounded-full bg-primary-container/20 flex items-center justify-center shrink-0 border border-primary-container/30">
          <img src="/BestLogo.svg" alt="Cerebro" className="w-6 h-6 opacity-80" />
        </div>
        <div className="space-y-3 pt-1">
          {(searchingWeb || searchingSources) && !content && (
            <div className="text-xs text-on-surface-variant italic flex items-center gap-1.5 mb-1">
              <span className="material-symbols-outlined text-[14px] animate-spin">sync</span>
              {searchingWeb
                ? "Searching the web…"
                : `Searching ${searchingSources?.count ?? 0} file${(searchingSources?.count ?? 0) !== 1 ? "s" : ""}…`
              }
            </div>
          )}
          {isStreaming ? (
            <p className="text-sm text-on-surface-variant whitespace-pre-wrap">
              {displayText}
              <span className="inline-block w-[2px] h-[16px] bg-primary-container ml-[1px] animate-pulse align-text-bottom" />
            </p>
          ) : (
            <MarkdownRenderer content={content} />
          )}
          {metadata && (
            <MessageFooter
              messageId={id}
              metadata={metadata}
              expandedPanel={expandedPanel}
            />
          )}

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
      </div>
    </div>
  );
}
