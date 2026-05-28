import { useRef, useState, KeyboardEvent, ChangeEvent } from "react";
import { useChatStore } from "../../stores/chat";
import { useServicesStore } from "../../stores/services";
import { useSystemStore, selectLlamaServerState, selectIsClaudeMode } from "../../stores/system";
import { queryAgent, queryAgentStream, confirmTool, AGENT_ID_MAP, uploadFiles } from "../../api/client";
import CommandAutocomplete from "./CommandAutocomplete";
import type { FileAttachment } from "../../api/types";

interface UploadedFile {
  file: File;
  preview: string;
}

export default function InputArea() {
  const [text, setText] = useState("");
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
  const servicesOff = useServicesStore((s) => s.servicesOff);
  const llamaServer = selectLlamaServerState(useSystemStore.getState());
  const isClaude = selectIsClaudeMode(status);
  const inputDisabled = isLoading || servicesOff;

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

    if (servicesOff) {
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

    // Build message content with file info
    let messageContent = query;
    const rawFilesToUpload = uploadedFiles.map((uf) => uf.file);
    if (uploadedFiles.length > 0) {
      const fileNames = uploadedFiles.map((uf) => uf.file.name).join(", ");
      messageContent = `${query}\n\n[Attached files: ${fileNames}]`;
    }

    addMessage({ role: "user", content: messageContent });
    clearAllFiles();
    setLoading(true);

    const ctrl = new AbortController();
    setAbortController(ctrl);

    const assistantId = addMessage({ role: "assistant", content: "" });
    let hasPendingConfirm = false;

    try {
      // 2. Upload and pre-process files via the secure backend endpoint
      let attachments: FileAttachment[] = [];
      if (rawFilesToUpload.length > 0) {
        attachments = await uploadFiles(rawFilesToUpload);
      }

      if (activeAgent === "calendar") {
        // Calendar agent uses tool execution which requires the non-streaming path.
        // Fake streaming UX by replaying the answer character-by-character.
        const response = await queryAgent(
          {
            question: query,
            agent: AGENT_ID_MAP[activeAgent],
            conversation_id: conversationId ?? undefined,
            attachments: attachments.length > 0 ? attachments : undefined,
          },
          ctrl.signal,
        );
        setConversationId(response.conversation_id);

        if (response.metadata?.pending_tool) {
          hasPendingConfirm = true;
          const convId = response.conversation_id;
          const toolName = response.metadata.pending_tool.name;
          const toolPath =
            typeof response.metadata.pending_tool.args?.path === "string"
              ? (response.metadata.pending_tool.args.path as string)
              : undefined;
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
            toolPath,
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
            attachments: attachments.length > 0 ? attachments : undefined,
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
          const toolPath =
            typeof metadata.pending_tool.args?.path === "string"
              ? (metadata.pending_tool.args.path as string)
              : undefined;
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
            toolPath,
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

  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const supportedTypes = [
      "image/jpeg",
      "image/png",
      "image/gif",
      "image/webp",
      "application/pdf",
      "text/plain",
      "text/csv",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/msword",
    ];

    const validFiles = files.filter((file) => supportedTypes.includes(file.type));
    
    const newFiles = validFiles.map((file) => ({
      file,
      preview: file.type.startsWith("image/") ? URL.createObjectURL(file) : "",
    }));

    setUploadedFiles((prev) => [...prev, ...newFiles]);
    
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeFile = (index: number) => {
    setUploadedFiles((prev) => {
      const updated = [...prev];
      if (updated[index].preview) {
        URL.revokeObjectURL(updated[index].preview);
      }
      updated.splice(index, 1);
      return updated;
    });
  };

  const clearAllFiles = () => {
    uploadedFiles.forEach((uf) => {
      if (uf.preview) URL.revokeObjectURL(uf.preview);
    });
    setUploadedFiles([]);
  };

  return (
    <div className="bg-[#1c1b23] border-t border-[#242736] p-3 shrink-0">
      {/* File preview area */}
      {uploadedFiles.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {uploadedFiles.map((uf, idx) => (
            <div
              key={idx}
              className="relative bg-[#242736] border border-[#344152] rounded p-2 flex items-center gap-2 text-xs text-[#e5e0ed]"
            >
              {uf.preview ? (
                <img src={uf.preview} alt={uf.file.name} className="w-12 h-12 rounded object-cover" />
              ) : (
                <div className="w-12 h-12 bg-[#1c1b23] rounded flex items-center justify-center text-[#8b8fa8]">
                  📄
                </div>
              )}
              <div className="flex flex-col flex-1 min-w-0">
                <span className="truncate font-medium">{uf.file.name}</span>
                <span className="text-[#8b8fa8]">{(uf.file.size / 1024).toFixed(1)} KB</span>
              </div>
              <button
                onClick={() => removeFile(idx)}
                className="ml-1 text-[#8b8fa8] hover:text-[#e5e0ed] transition-colors"
                aria-label="Remove file"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

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
          placeholder={
            servicesOff
              ? "Engine is off — use Turn on to chat again"
              : "Ask anything…"
          }
          rows={1}
          className="flex-1 bg-transparent border-none outline-none resize-none text-[14px] leading-[20px] text-[#e5e0ed] placeholder:text-[#8b8fa8] custom-scrollbar py-2 px-2 h-[44px]"
          aria-label="Chat input"
          disabled={inputDisabled}
        />

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,.pdf,.txt,.csv,.doc,.docx"
          onChange={handleFileSelect}
          className="hidden"
          aria-label="File upload"
        />

        {/* File upload button */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={inputDisabled}
          className="w-[44px] h-[44px] bg-[#242736] text-[#8b8fa8] rounded flex items-center justify-center transition-colors hover:bg-[#344152] hover:text-[#e5e0ed] active:opacity-80 disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Upload files"
          title="Upload files (images, PDFs, documents)"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        </button>

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
            disabled={!text.trim() || servicesOff}
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
