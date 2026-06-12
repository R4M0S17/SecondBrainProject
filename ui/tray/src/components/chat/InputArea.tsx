import { useRef, useState, KeyboardEvent, ChangeEvent } from "react";
import { useChatStore } from "../../stores/chat";
import { useSettingsStore } from "../../stores/settings";
import { useServicesStore } from "../../stores/services";
import { useSystemStore, selectLlamaServerState, selectIsClaudeMode } from "../../stores/system";
import { ApiError } from "../../api/errors";
import { queryAgent, queryAgentStream, confirmTool, AGENT_ID_MAP, uploadFiles } from "../../api/client";
import CommandAutocomplete from "./CommandAutocomplete";
import type { FileAttachment } from "../../api/types";

interface UploadedFile {
  file: File;
  preview: string;
}

const TEXT_MIME_TYPES = new Set([
  "text/plain",
  "text/markdown",
  "text/csv",
  "application/json",
  "text/x-python",
  "text/javascript",
  "text/typescript",
  "text/x-java",
  "text/x-c",
  "text/x-cpp",
  "text/yaml",
  "text/xml",
]);

const TEXT_EXTENSIONS = new Set([
  ".txt",
  ".md",
  ".csv",
  ".json",
  ".py",
  ".js",
  ".ts",
  ".tsx",
  ".jsx",
  ".html",
  ".css",
  ".xml",
  ".yaml",
  ".yml",
]);

function hasExtension(file: File, extensions: Set<string>): boolean {
  const lowerName = file.name.toLowerCase();
  for (const ext of extensions) {
    if (lowerName.endsWith(ext)) return true;
  }
  return false;
}

function isTextLikeFile(file: File): boolean {
  return TEXT_MIME_TYPES.has(file.type) || file.type.startsWith("text/") || hasExtension(file, TEXT_EXTENSIONS);
}

function isImageLikeFile(file: File): boolean {
  return file.type.startsWith("image/");
}

const MAX_IMAGE_DIM = 1024;
const JPEG_QUALITY = 0.85;

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = typeof reader.result === "string" ? reader.result : "";
      resolve(value.includes(",") ? value.split(",", 2)[1] ?? "" : value);
    };
    reader.onerror = () => reject(reader.error ?? new Error(`Failed to read ${file.name}`));
    reader.readAsDataURL(file);
  });
}

function resizeImage(
  dataUrl: string,
  maxDim: number = MAX_IMAGE_DIM,
  quality: number = JPEG_QUALITY,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      let { width, height } = img;
      const scale = maxDim / Math.max(width, height);
      if (scale >= 1) {
        resolve(dataUrl.split(",", 2)[1] ?? "");
        return;
      }
      width = Math.round(width * scale);
      height = Math.round(height * scale);
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!ctx) { resolve(dataUrl.split(",", 2)[1] ?? ""); return; }
      ctx.drawImage(img, 0, 0, width, height);
      resolve(canvas.toDataURL("image/jpeg", quality).split(",", 2)[1] ?? "");
    };
    img.onerror = () => reject(new Error("Failed to decode image"));
    img.src = dataUrl;
  });
}

async function buildLocalAttachment(file: File): Promise<FileAttachment | null> {
  if (isTextLikeFile(file)) {
    return {
      filename: file.name,
      mime_type: file.type || "text/plain",
      content: await file.text(),
      type: "text",
    };
  }

  if (isImageLikeFile(file)) {
    const raw = await readFileAsDataUrl(file);
    const dataUrl = `data:${file.type};base64,${raw}`;
    const resized = await resizeImage(dataUrl);
    return {
      filename: file.name,
      mime_type: "image/jpeg",
      content: resized,
      type: "image",
    };
  }

  return null;
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
    setSearchingWeb,
    setSearchingSources,
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
    const ta = textareaRef.current;
    if (ta) {
      const lineHeight = 20;
      const padding = 12;
      const minHeight = lineHeight + padding;
      if (!val) {
        ta.style.height = `${minHeight}px`;
      } else {
        ta.style.height = `${minHeight}px`;
        ta.style.height = `${Math.min(ta.scrollHeight, 4 * lineHeight + padding)}px`;
      }
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

    if (query === "/model") {
      const model = useSettingsStore.getState().activeModel || "local";
      addMessage({ role: "user", content: "/model" });
      addMessage({ role: "assistant", content: `Currently running model: **${model}**` });
      setText("");
      setShowAutocomplete(false);
      if (textareaRef.current) textareaRef.current.style.height = "44px";
      return;
    }

    setText("");
    setShowAutocomplete(false);
    if (textareaRef.current) textareaRef.current.style.height = "44px";

    let messageContent = query;
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
      let attachments: FileAttachment[] = [];
      const localAttachments = (
        await Promise.all(uploadedFiles.map((uf) => buildLocalAttachment(uf.file)))
      ).filter((att): att is FileAttachment => att !== null);

      const filesToUpload = uploadedFiles
        .map((uf) => uf.file)
          .filter((file) => !isTextLikeFile(file) && !isImageLikeFile(file));

      attachments = [...localAttachments];

      if (filesToUpload.length > 0) {
        try {
          const remoteAttachments = await uploadFiles(filesToUpload);
          attachments = [...attachments, ...remoteAttachments];
        } catch (e: unknown) {
          const apiErr = e instanceof ApiError ? e : null;
          if (apiErr?.status !== 404 || attachments.length === 0) {
            throw e;
          }
        }
      }

      if (activeAgent === "calendar") {
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
          if (toolName === "web_search" || toolName === "web_fetch") {
            setSearchingWeb(true);
          }
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
        let streamConversationId: string | undefined;
        const metadata = await queryAgentStream(
          {
            question: query,
            agent: AGENT_ID_MAP[activeAgent],
            conversation_id: conversationId ?? undefined,
            attachments: attachments.length > 0 ? attachments : undefined,
          },
          (token) => {
            if (useChatStore.getState().searchingSources) {
              useChatStore.getState().setSearchingSources(null);
            }
            if (useChatStore.getState().searchingWeb) {
              useChatStore.getState().setSearchingWeb(false);
            }
            appendToken(assistantId, token);
          },
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
          (event) => {
            setSearchingSources({ count: event.episode_count, sources: event.sources });
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

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const clearAllFiles = () => {
    uploadedFiles.forEach((uf) => {
      if (uf.preview) URL.revokeObjectURL(uf.preview);
    });
    setUploadedFiles([]);
  };

  const engineOk = status?.engine_ok ?? false;
  const latency = status?.p95_latency_ms ?? 0;

  return (
    <div className="relative w-full shrink-0">
      <div className="input-glow flex items-center bg-surface-container-low border border-outline-variant/50 rounded-xl p-2 transition-all duration-300">
        {/* Command autocomplete */}
        {showAutocomplete && (
          <CommandAutocomplete query={text} onSelect={handleCommandSelect} />
        )}

        {/* Add / file upload button */}
        <button
          onClick={() => fileInputRef.current?.click()}
          className="p-2 text-on-surface-variant hover:text-primary-container transition-colors"
          aria-label="Add files"
          title="Upload files (images, PDFs, documents)"
        >
          <span className="material-symbols-outlined text-[20px]">add</span>
        </button>

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

        <textarea
          ref={textareaRef}
          rows={1}
          className="flex-1 bg-transparent border-none outline-none resize-none text-on-surface text-sm focus:ring-0 focus:outline-none placeholder:text-outline/50 px-2 custom-scrollbar"
          placeholder={
            servicesOff
              ? "Engine is off — use Turn on to chat again"
              : "Ask Cerebro or issue a command..."
          }
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={inputDisabled}
        />

        <div className="flex items-center gap-2 pr-2 text-on-surface-variant">
          {/* Mic button */}
          <button className="p-2 hover:text-primary transition-colors" aria-label="Voice input" title="Voice input">
            <span className="material-symbols-outlined text-[20px]">mic</span>
          </button>

          {isLoading ? (
            <button
              onClick={cancelRequest}
              className="p-2 bg-primary-container/10 text-primary-container rounded-lg border border-primary-container/20 hover:bg-primary-container/20 transition-colors"
              aria-label="Cancel request"
              title="Cancel (Esc)"
            >
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>
          ) : (
            <button
              onClick={() => void send()}
              disabled={!text.trim() || isLoading || servicesOff}
              className="p-2 bg-primary-container/10 text-primary-container rounded-lg border border-primary-container/20 hover:bg-primary-container/20 transition-colors disabled:opacity-30"
              aria-label="Send message"
            >
              <span className="material-symbols-outlined text-[18px]">send</span>
            </button>
          )}
        </div>
      </div>

      {/* Status footer */}
      <div className="text-center mt-3 text-xs text-outline/50 font-label-mono">
        Engine Status: {engineOk ? "Active" : "Offline"} • Latency {latency}ms
      </div>
    </div>
  );
}
