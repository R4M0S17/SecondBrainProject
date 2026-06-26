import { useRef, useState, useEffect, KeyboardEvent, ChangeEvent } from "react";
import { useTranslation } from "react-i18next";
import { useChatStore } from "../../stores/chat";
import { useSettingsStore } from "../../stores/settings";
import { useServicesStore, needsLocalEngine } from "../../stores/services";
import { useSystemStore, selectLlamaServerState, selectIsClaudeMode } from "../../stores/system";
import { useTabStore } from "../../stores/tab";
import { ApiError } from "../../api/errors";
import { queryAgent, queryAgentStream, confirmTool, AGENT_ID_MAP, uploadFiles, startIndex, getConfig } from "../../api/client";
import CommandAutocomplete, { buildCommands } from "./CommandAutocomplete";
import type { FileAttachment } from "../../api/types";
import { AGENTS } from "../../api/types";
import { isTextLikeFile, isImageLikeFile, buildLocalAttachment } from "../../utils/fileProcessing";

interface UploadedFile {
  file: File;
  preview: string;
}

export default function InputArea() {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [selectedCmdIndex, setSelectedCmdIndex] = useState(-1);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeTab = useTabStore((s) => s.activeTab);

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
    clearMessages,
  } = useChatStore();
  const { refresh, setSwapEvent, status } = useSystemStore();
  const backendReady = useServicesStore((s) => s.backendReady);
  const llamaServer = selectLlamaServerState(useSystemStore.getState());
  const isClaude = selectIsClaudeMode(status);
  const engineOk = status?.engine_ok ?? false;
  const needsEngine = needsLocalEngine(status?.provider);
  const inputDisabled = isLoading || !backendReady;

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setText(val);
    const show = val.startsWith("/");
    setShowAutocomplete(show);
    if (show) {
      const matches = buildCommands(t).filter((c) => c.name.startsWith(val.toLowerCase()));
      setSelectedCmdIndex(matches.length > 0 ? 0 : -1);
    } else {
      setSelectedCmdIndex(-1);
    }
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
    const matches = showAutocomplete
      ? buildCommands(t).filter((c) => c.name.startsWith(text.toLowerCase()))
      : [];

    if (showAutocomplete && matches.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedCmdIndex((prev) => (prev < matches.length - 1 ? prev + 1 : 0));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedCmdIndex((prev) => (prev > 0 ? prev - 1 : matches.length - 1));
        return;
      }
      if (e.key === "Tab") {
        e.preventDefault();
        const idx = selectedCmdIndex >= 0 ? selectedCmdIndex : 0;
        handleCommandSelect(matches[idx].name);
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
      return;
    }
    if (e.key === "Escape") {
      if (showAutocomplete) {
        setShowAutocomplete(false);
        setSelectedCmdIndex(-1);
      } else if (isLoading) {
        cancelRequest();
      } else {
        textareaRef.current?.blur();
      }
    }
  };

  const sendQuery = async (query: string) => {
    if (!query || isLoading) return;

    if (!backendReady) return;

    if (!isClaude && needsEngine && !engineOk && llamaServer === "restarting") {
      addMessage({
        role: "assistant",
        content: t("input.engine_restarting"),
      });
      return;
    }

    const matchedCmd = buildCommands(t).find((c) => c.name === query);
    if (matchedCmd) {
      handleCommand(matchedCmd);
      return;
    }

    setText("");
    setShowAutocomplete(false);
    if (textareaRef.current) textareaRef.current.style.height = "44px";

    let messageContent = query;
    if (uploadedFiles.length > 0) {
      const fileNames = uploadedFiles.map((uf) => uf.file.name).join(", ");
      messageContent = `${query}\n\n${t("input.attached_files", { names: fileNames })}`;
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
                content: t("error.generic", { message: (e as Error).message ?? "Confirmation failed" }),
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
                content: t("error.generic", { message: (e as Error).message ?? "Confirmation failed" }),
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
            ? t("error.backend_unreachable")
            : t("error.generic", { message: msg }),
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

  const send = async () => {
    const query = text.trim();
    void sendQuery(query);
  };

  const handleCommand = async (cmd: { name: string; description: string }) => {
    addMessage({ role: "user", content: cmd.name });
    setText("");
    setShowAutocomplete(false);
    setSelectedCmdIndex(-1);
    if (textareaRef.current) textareaRef.current.style.height = "44px";

    switch (cmd.name) {
      case "/help": {
        const cmdList = buildCommands(t).map(
          (c) => `\`${c.name}\` — ${c.description}`,
        ).join("\n");
        addMessage({
          role: "assistant",
          content: t("commands.help_response", { list: cmdList }),
        });
        break;
      }
      case "/clear": {
        clearMessages();
        addMessage({ role: "assistant", content: t("commands.clear_response") });
        break;
      }
      case "/model": {
        const model = useSettingsStore.getState().activeModel || "local";
        addMessage({
          role: "assistant",
          content: t("commands.model_response", { model }),
        });
        break;
      }
      case "/status": {
        const s = useSystemStore.getState().status;
        if (!s) {
          addMessage({ role: "assistant", content: t("commands.status_unavailable") });
        } else {
          addMessage({
            role: "assistant",
            content: t("commands.status_response", {
              engine: s.engine_ok ? t("commands.engine_active") : t("commands.engine_offline"),
              model: s.model,
              provider: s.provider,
              latency: s.p95_latency_ms,
              ram: `${s.ram_used_gb.toFixed(1)}/${s.ram_total_gb.toFixed(1)} GB (${s.ram_pressure})`,
              cpu: s.cpu_percent,
              files: s.indexed_files,
              queries: s.queries_total,
              hits: s.memory_hits,
              calls: s.tool_call_count,
            }),
          });
        }
        break;
      }
      case "/agents": {
        const agentList = AGENTS.map((a) => `\`${a.id}\` — ${a.label}`).join("\n");
        addMessage({
          role: "assistant",
          content: t("commands.agents_response", { list: agentList }),
        });
        break;
      }
      case "/index": {
        const indexMsg = addMessage({
          role: "assistant",
          content: t("commands.index_started"),
        });
        try {
          const result = await startIndex([]);
          updateMessage(indexMsg, {
            content: t("commands.index_job_id", { job_id: result.job_id }),
          });
        } catch (e: unknown) {
          updateMessage(indexMsg, {
            content: t("commands.index_failed", { message: (e as Error).message }),
          });
        }
        break;
      }
      case "/memory": {
        const s = useSystemStore.getState().status;
        addMessage({
          role: "assistant",
          content: s
            ? t("commands.memory_response", { hits: s.memory_hits, files: s.indexed_files })
            : t("commands.status_unavailable"),
        });
        break;
      }
      case "/export": {
        const { messages } = useChatStore.getState();
        const blob = new Blob(
          [
            JSON.stringify(
              {
                exported_at: new Date().toISOString(),
                model: useSettingsStore.getState().activeModel,
                messages: messages.map((m) => ({
                  role: m.role,
                  content: m.content,
                  timestamp: m.timestamp,
                })),
              },
              null,
              2,
            ),
          ],
          { type: "application/json" },
        );
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `cerebro-export-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
        addMessage({ role: "assistant", content: t("commands.export_response") });
        break;
      }
      case "/refresh": {
        void refresh();
        addMessage({ role: "assistant", content: t("commands.refresh_response") });
        break;
      }
      case "/settings": {
        try {
          const config = await getConfig();
          const lines = Object.entries(config).map(
            ([k, v]) => `\`${k}\`: ${typeof v === "string" ? v : JSON.stringify(v)}`,
          );
          addMessage({
            role: "assistant",
            content: t("commands.settings_response", { lines: lines.join("\n") }),
          });
        } catch {
          addMessage({
            role: "assistant",
            content: t("commands.settings_unavailable"),
          });
        }
        break;
      }
    }
  };

  const handleCommandSelect = (cmd: string) => {
    setText(cmd + " ");
    setShowAutocomplete(false);
    setSelectedCmdIndex(-1);
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

  useEffect(() => {
    if (activeTab !== "chat") return;
    const action = useChatStore.getState().consumePendingChatAction();
    if (!action) return;
    setText(action.query);
    if (action.autoSend) {
      requestAnimationFrame(() => sendQuery(action.query));
    }
  }, [activeTab]);

  const latency = status?.p95_latency_ms ?? 0;

  return (
    <div className="relative w-full shrink-0">
      <div className="input-glow flex items-center bg-surface-container-low border border-outline-variant/50 rounded-xl p-2 transition-all duration-300">
        {/* Command autocomplete */}
        {showAutocomplete && (
          <CommandAutocomplete query={text} selectedIndex={selectedCmdIndex} onSelect={handleCommandSelect} />
        )}

        {/* Add / file upload button */}
        <button
          onClick={() => fileInputRef.current?.click()}
          className="p-2 text-on-surface-variant hover:text-primary-container transition-colors"
          aria-label={t("input.add_files")}
          title={t("input.file_upload")}
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
          aria-label={t("input.file_upload")}
        />

        <textarea
          ref={textareaRef}
          rows={1}
          aria-label={t("chat.placeholder")}
          className="flex-1 bg-transparent border-none outline-none resize-none text-on-surface text-sm focus:ring-0 focus:outline-none placeholder:text-outline/50 px-2 custom-scrollbar"
          placeholder={
            !backendReady
              ? t("chat.backend_off_placeholder")
              : needsEngine && !engineOk
                ? t("chat.engine_off_placeholder")
                : t("chat.placeholder")
          }
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={inputDisabled}
        />

        <div className="flex items-center gap-2 pr-2 text-on-surface-variant">
          {/* Mic button */}
          <button className="p-2 hover:text-primary transition-colors" aria-label={t("input.voice_input")} title={t("input.voice_input")}>
            <span className="material-symbols-outlined text-[20px]">mic</span>
          </button>

          {isLoading ? (
            <button
              onClick={cancelRequest}
              className="p-1.5 bg-primary-container/10 text-primary-container rounded-lg border border-primary-container/20 hover:bg-primary-container/20 transition-colors"
              aria-label={t("chat.cancel")}
              title={t("chat.cancel")}
            >
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>
          ) : (
            <button
              onClick={() => void send()}
              disabled={!text.trim() || isLoading || !backendReady}
              className="p-1.5 bg-primary-container/10 text-primary-container rounded-lg border border-primary-container/20 hover:bg-primary-container/20 transition-colors disabled:opacity-30"
              aria-label={t("chat.send")}
            >
              <span className="material-symbols-outlined text-[18px]">send</span>
            </button>
          )}
        </div>
      </div>

      {/* Status footer */}
      <div className="text-center mt-3 text-xs text-outline/50 font-label-mono">
        {t("input.engine_status", {
          status: engineOk ? t("commands.engine_active") : t("commands.engine_offline"),
          latency,
        })}
      </div>
    </div>
  );
}
