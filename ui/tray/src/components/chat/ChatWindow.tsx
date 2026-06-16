import { useCallback, useEffect, useRef, useState } from "react";
import { useChatStore } from "../../stores/chat";
import { useSettingsStore } from "../../stores/settings";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";
import WarningToast from "./WarningToast";
import InputArea from "./InputArea";
import FastPathToggles from "./FastPathToggles";
import ConfirmModal from "../shared/ConfirmModal";
import SwapBanner from "./SwapBanner";

interface ChatWindowProps {
  className?: string;
}

export default function ChatWindow({ className = "" }: ChatWindowProps) {
  const { messages, isLoading, pendingConfirmation } = useChatStore();
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const userScrolledRef = useRef(false);
  const prevMsgCountRef = useRef(messages.length);
  const [dismissedWarnings, setDismissedWarnings] = useState<Set<string>>(
    new Set()
  );

  useEffect(() => {
    const newMsgCount = messages.length;
    const newUserMsg = newMsgCount > prevMsgCountRef.current && messages[newMsgCount - 1]?.role === "user";
    prevMsgCountRef.current = newMsgCount;

    const shouldScroll =
      newUserMsg ||
      (!isLoading && !userScrolledRef.current) ||
      (isNearBottomRef.current && !userScrolledRef.current);

    if (shouldScroll) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading]);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const threshold = 150;
    const nearBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
    isNearBottomRef.current = nearBottom;
    userScrolledRef.current = !nearBottom;
  }, []);

  const activeModel = useChatStore((s) => {
    for (let i = s.messages.length - 1; i >= 0; i--) {
      const m = s.messages[i];
      if (m.metadata?.model_used) return m.metadata.model_used;
    }
    return useSettingsStore.getState().activeModel || "local";
  });

  const warnings = messages
    .filter(
      (m) => m.metadata?.warnings?.length && !dismissedWarnings.has(m.id)
    )
    .map((m) => ({ id: m.id, text: m.metadata!.warnings[0] }));

  return (
    <div className={`flex flex-col ${className}`}>
      <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto pr-4 space-y-6 scrollbar-auto min-h-0">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-3 opacity-40">
            <img src="/BestLogo.svg" alt="Cerebro" className="w-12 h-12 opacity-60" />
            <p className="text-sm text-on-surface-variant">Ask anything about your notes…</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            isStreaming={isLoading && i === messages.length - 1 && msg.role === "assistant"}
          />
        ))}

        {isLoading && <TypingIndicator model={activeModel} />}

        <div ref={bottomRef} />
      </div>

      {warnings.length > 0 && (
        <div className="px-4 pb-2 space-y-1">
          {warnings.map((w) => (
            <WarningToast
              key={w.id}
              message={w.text}
              onDismiss={() =>
                setDismissedWarnings((prev) => new Set([...prev, w.id]))
              }
            />
          ))}
        </div>
      )}

      <SwapBanner />

      <FastPathToggles />

      <InputArea />

      {pendingConfirmation && (
        <ConfirmModal
          toolName={pendingConfirmation.toolName}
          toolPath={pendingConfirmation.toolPath}
          toolAction={pendingConfirmation.toolAction}
          toolSize={pendingConfirmation.toolSize}
          warningText={pendingConfirmation.warningText}
          onApprove={pendingConfirmation.onApprove}
          onDeny={pendingConfirmation.onDeny}
        />
      )}
    </div>
  );
}
