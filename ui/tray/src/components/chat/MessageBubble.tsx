import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Copy, Check } from "lucide-react";
import type { Message } from "../../stores/chat";
import { useChatStore } from "../../stores/chat";
import { useMemoryStore } from "../../stores/memory";
import { useTabStore } from "../../stores/tab";
import MarkdownRenderer from "./MarkdownRenderer";
import MessageFooter from "./MessageFooter";
import SourcesPanel from "./SourcesPanel";
import ToolHistoryPanel from "./ToolHistoryPanel";
import MemoryPanel from "./MemoryPanel";

function formatTime(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) {
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function useTypewriter(fullText: string, isStreaming: boolean) {
  const [displayed, setDisplayed] = useState(0);
  const fullTextRef = useRef(fullText);
  fullTextRef.current = fullText;

  useEffect(() => {
    if (!isStreaming) {
      setDisplayed(fullText.length);
      return;
    }
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
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const { role, content, metadata, expandedPanel, id, timestamp } = message;
  const typewriterLen = useTypewriter(content, !!isStreaming);
  const displayText = isStreaming ? content.slice(0, typewriterLen) : content;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard not available
    }
  };

  if (role === "user") {
    return (
      <div className="flex justify-end" role="article" aria-label="Your message">
        <div className="max-w-[70%]">
          <div className="bg-primary-container/15 border border-primary-container/25 rounded-2xl rounded-tr-sm p-4 text-sm text-on-surface">
            {content}
          </div>
          <div className="text-[10px] text-outline/50 text-right mt-1 px-1">
            {formatTime(timestamp)}
          </div>
        </div>
      </div>
    );
  }

  const searchingSources = useChatStore((s) => s.searchingSources);
  const searchingWeb = useChatStore((s) => s.searchingWeb);
  const [savingMemory, setSavingMemory] = useState(false);
  const [memorySaved, setMemorySaved] = useState(false);

  const handleRegenerate = () => {
    const messages = useChatStore.getState().messages;
    const msgIndex = messages.findIndex((m) => m.id === id);
    if (msgIndex < 1) return;
    const prevUserMsg = messages[msgIndex - 1];
    if (prevUserMsg.role !== "user") return;
    useChatStore.getState().setPendingChatAction({
      query: prevUserMsg.content,
      autoSend: true,
    });
  };

  const handleAddToMemory = async () => {
    setSavingMemory(true);
    try {
      await useMemoryStore.getState().addEpisode(content, ["chat"]);
      setMemorySaved(true);
      setTimeout(() => setMemorySaved(false), 2000);
    } catch {
      // ignore
    } finally {
      setSavingMemory(false);
    }
  };

  return (
    <div className="flex justify-start group" role="article" aria-label="Assistant message">
      <div className="flex gap-4 max-w-[80%]">
        <div className="flex flex-col items-center gap-1 shrink-0">
          <div className="w-8 h-8 rounded-full bg-primary-container/20 flex items-center justify-center border border-primary-container/30">
            <img src="/BestLogo.svg" alt="Cerebro" className="w-6 h-6 opacity-80" />
          </div>
          <button
            onClick={handleCopy}
            className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-surface-container text-outline hover:text-on-surface"
            aria-label={t("chat.copy_message")}
            title={t("chat.copy_message")}
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
          </button>
        </div>
        <div className="space-y-3 pt-1">
          {(searchingWeb || searchingSources) && !content && (
            <div className="text-xs text-on-surface-variant italic flex items-center gap-1.5 mb-1">
              <span className="material-symbols-outlined text-[14px] animate-spin">sync</span>
              {searchingWeb
                ? t("searching.web")
                : t("searching.files", { count: searchingSources?.count ?? 0 })
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
          {!isStreaming && (
            <div className="text-[10px] text-outline/50">
              {timestamp ? formatTime(timestamp) : ""}
            </div>
          )}
          {!isStreaming && (
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 text-[10px] font-medium text-outline hover:text-on-surface px-2 py-1 rounded hover:bg-surface-container transition-colors"
                title={t("chat.copy_message")}
              >
                {copied ? <Check size={12} /> : <Copy size={12} />}
                {copied ? t("chat.copied") : t("chat.copy")}
              </button>
              <button
                onClick={handleRegenerate}
                className="flex items-center gap-1 text-[10px] font-medium text-outline hover:text-on-surface px-2 py-1 rounded hover:bg-surface-container transition-colors"
                title={t("chat.regenerate")}
              >
                <span className="material-symbols-outlined text-[12px]">refresh</span>
                {t("chat.regenerate")}
              </button>
              <button
                onClick={() => void handleAddToMemory()}
                disabled={savingMemory}
                className="flex items-center gap-1 text-[10px] font-medium text-outline hover:text-on-surface px-2 py-1 rounded hover:bg-surface-container transition-colors disabled:opacity-50"
                title={t("chat.save_to_memory")}
              >
                <span className="material-symbols-outlined text-[12px]">{memorySaved ? "check" : "psychology"}</span>
                {memorySaved ? t("chat.saved") : savingMemory ? "..." : t("chat.save_to_memory")}
              </button>
            </div>
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
            <MemoryPanel
              memory={metadata.memory_retrieved}
              onViewAll={() => {
                if (metadata.memory_retrieved[0]) {
                  useMemoryStore.getState().setHighlightedId(metadata.memory_retrieved[0].id);
                }
                useTabStore.getState().setTab("memory");
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
