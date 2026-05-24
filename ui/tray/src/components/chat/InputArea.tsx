import { useRef, useState, KeyboardEvent, ChangeEvent } from "react";
import { useChatStore } from "../../stores/chat";
import { useSystemStore, selectLlamaServerState, selectIsClaudeMode } from "../../stores/system";
import { queryAgent, queryAgentStream, confirmTool, AGENT_ID_MAP } from "../../api/client";
import CommandAutocomplete from "./CommandAutocomplete";

export default function InputArea() {
  const [text, setText] = useState("");
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const {
    addMessage,
    updateMessage,
    appendToken,
    setLoading,
    isLoading,
    cancelRequest,
    setAbortController,
    setPendingConfirmation,
    activeAgent,
    conversationId,
    setConversationId,
  } = useChatStore();
  const { refresh, setSwapEvent, status } = useSystemStore();
  const llamaServer = selectLlamaServerState(useSystemStore.getState());
  const isClaude = selectIsClaudeMode(status);

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setText(val);
    setShowAutocomplete(val.startsWith("/"));
    // Auto-grow textarea (max 4 lines)
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "44px";
      ta.style.height = `${Math.min(ta.scrollHeight, 88)}px`;
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
    if (e.key === "Escape") {
      if (isLoading) {
        cancelRequest();
      } else {
        textareaRef.current?.blur();
      }
    }
  };

  const send = async () => {
    const query = text.trim();
    if (!query || isLoading) return;

    if (!isClaude && llamaServer === "down") {
      addMessage({
        role: "assistant",
        content:
          "El motor de inferencia no está disponible. Se está reintentando la conexión; espera unos segundos e inténtalo de nuevo.",
      });
      return;
    }

    if (!isClaude && llamaServer === "restarting") {
      addMessage({
        role: "assistant",
        content: "El motor de inferencia se está reiniciando. Espera un momento e inténtalo de nuevo.",
      });
      return;
    }

    setText("");
    setShowAutocomplete(false);
    if (textareaRef.current) textareaRef.current.style.height = "44px";

    addMessage({ role: "user", content: query });
    setLoading(true);

    const ctrl = new AbortController();
    setAbortController(ctrl);

    const assistantId = addMessage({ role: "assistant", content: "" });
    let hasPendingConfirm = false;

    try {
      if (activeAgent === "calendar") {
        // Calendar agent uses tool execution which requires the non-streaming path.
        // Fake streaming UX by replaying the answer character-by-character.
        const response = await queryAgent(
          {
            question: query,
            agent: AGENT_ID_MAP[activeAgent],
            conversation_id: conversationId ?? undefined,
          },
          ctrl.signal,
        );
        setConversationId(response.conversation_id);

        if (response.metadata?.pending_tool) {
          hasPendingConfirm = true;
          const convId = response.conversation_id;
          const toolName = response.metadata.pending_tool.name;
          updateMessage(assistantId, { metadata: response.metadata });

          const handleDecision = async (decision: "approve" | "deny") => {
            setPendingConfirmation(null);
            setLoading(true);
            try {
              const result = await confirmTool(convId, decision);
              updateMessage(assistantId, { content: result.answer, metadata: result.metadata });
            } catch (e: unknown) {
              updateMessage(assistantId, {
                content: `Error: ${(e as Error).message ?? "Confirmation failed"}`,
              });
            } finally {
              setLoading(false);
              setAbortController(null);
              void refresh();
            }
          };

          setPendingConfirmation({
            toolName,
            onApprove: () => { void handleDecision("approve"); },
            onDeny: () => { void handleDecision("deny"); },
          });
        } else {
          for (const char of response.answer) {
            if (ctrl.signal.aborted) break;
            appendToken(assistantId, char);
            await new Promise<void>((res) => setTimeout(res, 10));
          }
          updateMessage(assistantId, { metadata: response.metadata });
        }
      } else {
        let conversationId: string | undefined;
        let streamConversationId: string | undefined;
        const metadata = await queryAgentStream(
          {
            question: query,
            agent: AGENT_ID_MAP[activeAgent],
            conversation_id: conversationId ?? undefined,
          },
          (token) => appendToken(assistantId, token),
          ctrl.signal,
          (id) => {
            streamConversationId = id;
            setConversationId(id);
          },
          (event) => {
            if (event.phase === "started") {
              setSwapEvent(event);
            } else {
              setTimeout(() => setSwapEvent(null), 1500);
            }
          },
        );

        if (metadata?.pending_tool && streamConversationId) {
          hasPendingConfirm = true;
          const convId = streamConversationId;
          const toolName = metadata.pending_tool.name;
          updateMessage(assistantId, { metadata });

          const handleDecision = async (decision: "approve" | "deny") => {
            setPendingConfirmation(null);
            setLoading(true);
            try {
              const result = await confirmTool(convId, decision);
              updateMessage(assistantId, { content: result.answer, metadata: result.metadata });
            } catch (e: unknown) {
              updateMessage(assistantId, {
                content: `Error: ${(e as Error).message ?? "Confirmation failed"}`,
              });
            } finally {
              setLoading(false);
              setAbortController(null);
              void refresh();
            }
          };

          setPendingConfirmation({
            toolName,
            onApprove: () => { void handleDecision("approve"); },
            onDeny: () => { void handleDecision("deny"); },
          });
        } else if (metadata) {
          updateMessage(assistantId, { metadata });
        }
      }
    } catch (e: unknown) {
      if ((e as Error).name !== "AbortError") {
        const msg = (e as Error).message ?? "Request failed";
        const isNetworkDown =
          msg === "Load failed" ||
          msg === "Failed to fetch" ||
          msg === "Network request failed";
        updateMessage(assistantId, {
          content: isNetworkDown
            ? "Cannot reach the backend. Make sure `make run` is running on port 7842."
            : `Error: ${msg}`,
        });
      }
    } finally {
      if (!hasPendingConfirm) {
        setLoading(false);
        setAbortController(null);
        void refresh();
      }
    }
  };

  const handleCommandSelect = (cmd: string) => {
    setText(cmd + " ");
    setShowAutocomplete(false);
    textareaRef.current?.focus();
  };

  return (
    <div className="bg-[#1c1b23] border-t border-[#242736] p-3 shrink-0">
      <div className="relative flex items-end gap-2 bg-[#201f27] border border-[#242736] rounded p-1 focus-within:border-[#94a3b8] transition-colors">
        {/* Command autocomplete */}
        {showAutocomplete && (
          <CommandAutocomplete query={text} onSelect={handleCommandSelect} />
        )}

        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything…"
          rows={1}
          className="flex-1 bg-transparent border-none outline-none resize-none text-[14px] leading-[20px] text-[#e5e0ed] placeholder:text-[#8b8fa8] custom-scrollbar py-2 px-2 h-[44px]"
          aria-label="Chat input"
          disabled={isLoading}
        />

        {isLoading ? (
          <button
            onClick={cancelRequest}
            className="w-[44px] h-[44px] bg-[#444652] text-[#e5e0ed] rounded flex items-center justify-center transition-colors hover:bg-[#5a5768] active:opacity-80"
            aria-label="Cancel request"
            title="Cancel (Esc)"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="1" />
            </svg>
          </button>
        ) : (
          <button
            onClick={() => void send()}
            disabled={!text.trim()}
            className={`w-[44px] h-[44px] rounded flex items-center justify-center transition-colors active:opacity-80 ${
              text.trim()
                ? "bg-[#94a3b8] hover:bg-[#6b7a90] text-[#0f1117]"
                : "bg-[#242736] text-[#8b8fa8] cursor-not-allowed"
            }`}
            aria-label="Send message"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
