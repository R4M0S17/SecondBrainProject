import { useEffect, useRef, useState } from "react";
import { useChatStore } from "../../stores/chat";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";
import WarningToast from "./WarningToast";
import InputArea from "./InputArea";
import ConfirmModal from "../shared/ConfirmModal";
import SwapBanner from "./SwapBanner";

interface ChatWindowProps {
  className?: string;
}

export default function ChatWindow({ className = "" }: ChatWindowProps) {
  const { messages, isLoading, pendingConfirmation } = useChatStore();
  const bottomRef = useRef<HTMLDivElement>(null);
  const [dismissedWarnings, setDismissedWarnings] = useState<Set<string>>(
    new Set()
  );

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const activeModel = useChatStore((s) => {
    for (let i = s.messages.length - 1; i >= 0; i--) {
      const m = s.messages[i];
      if (m.metadata?.model_used) return m.metadata.model_used;
    }
    return "phi3:mini";
  });

  // Collect warnings from messages
  const warnings = messages
    .filter(
      (m) => m.metadata?.warnings?.length && !dismissedWarnings.has(m.id)
    )
    .map((m) => ({ id: m.id, text: m.metadata!.warnings[0] }));

  return (
    <div className={`flex flex-col ${className}`}>
      {/* Scrollable message area */}
      <main className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-6 bg-[#0e0d15] min-h-0">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-3 opacity-40">
            <svg className="w-10 h-10 text-[#94a3b8]" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C8.13 2 5 5.13 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26C17.81 13.47 19 11.38 19 9c0-3.87-3.13-7-7-7zm0 2c2.76 0 5 2.24 5 5 0 1.85-1.01 3.47-2.5 4.33-.31.18-.5.51-.5.87V16h-4v-1.8c0-.36-.19-.69-.5-.87C8.01 12.47 7 10.85 7 9c0-2.76 2.24-5 5-5zm-1 13h2v1h-2v-1z" />
            </svg>
            <p className="text-[14px] text-[#8b8fa8]">Ask anything about your notes…</p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {isLoading && <TypingIndicator model={activeModel} />}

        <div ref={bottomRef} />
      </main>

      {/* Warning toasts (just above input) */}
      {warnings.length > 0 && (
        <div className="px-4 pb-2 space-y-1 bg-[#0e0d15]">
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

      {/* Model swap banner */}
      <SwapBanner />

      {/* Input area */}
      <InputArea />

      {/* Confirm modal */}
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
