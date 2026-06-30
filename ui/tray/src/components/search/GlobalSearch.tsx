import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { searchConversations, searchDocuments, recallMemory } from "../../api/client";
import { useTabStore } from "../../stores/tab";
import { useChatStore } from "../../stores/chat";
import { useHistoryStore } from "../../stores/history";
import type { ConversationSummary } from "../../api/types";

interface SearchResult {
  type: "conversation" | "document" | "memory";
  label: string;
  sublabel: string;
  icon: string;
  onSelect: () => void;
}

export default function GlobalSearch({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const [convs, docs, mem] = await Promise.all([
        searchConversations(q).catch(() => [] as ConversationSummary[]),
        searchDocuments({ query: q, mode: "chunks", top_k: 5 }).catch(() => null),
        recallMemory(q).catch(() => null),
      ]);

      const items: SearchResult[] = [];

      for (const c of convs) {
        items.push({
          type: "conversation",
          label: c.first_user_message || "Untitled",
          sublabel: `${c.message_count} messages · ${new Date(c.last_active).toLocaleDateString()}`,
          icon: "chat",
          onSelect: () => {
            useHistoryStore.getState().select(c.conv_id);
            useTabStore.getState().setTab("chat");
            onClose();
          },
        });
      }

      if (docs?.hits) {
        const seen = new Set<string>();
        for (const h of docs.hits) {
          const key = `${h.filename}:${h.chunk_index}`;
          if (seen.has(key)) continue;
          seen.add(key);
          items.push({
            type: "document",
            label: h.filename,
            sublabel: h.snippet.slice(0, 120),
            icon: "description",
            onSelect: () => {
              useTabStore.getState().setTab("chat");
              useChatStore.getState().setPendingChatAction({ query: `Find more about "${h.filename}" from my documents`, autoSend: false });
              onClose();
            },
          });
        }
      }

      if (mem?.results) {
        for (const r of mem.results) {
          items.push({
            type: "memory",
            label: r.episode.content.slice(0, 80),
            sublabel: `Memory · ${r.episode.tags?.join(", ") || ""}`,
            icon: "psychology",
            onSelect: () => {
              useTabStore.getState().setTab("memory");
              onClose();
            },
          });
        }
      }

      setResults(items);
      setSelectedIdx(0);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [onClose]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => void doSearch(query), 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, doSearch]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIdx((prev) => Math.min(prev + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIdx((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter" && results[selectedIdx]) {
      results[selectedIdx].onSelect();
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-start justify-center pt-[15vh]" onClick={onClose}>
      <div className="fixed inset-0 bg-black/50" />
      <div
        className="relative w-full max-w-[560px] bg-surface-container-high rounded-xl shadow-2xl border border-outline-variant/40 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b border-outline-variant/20">
          <span className="material-symbols-outlined text-[18px] text-outline">search</span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("search.global_placeholder")}
            className="flex-1 bg-transparent border-none outline-none text-sm text-on-surface placeholder:text-outline/50"
          />
          {loading && <span className="w-4 h-4 border-2 border-outline border-t-transparent rounded-full animate-spin" />}
          <kbd className="text-[10px] text-outline/60 border border-outline-variant/20 rounded px-1.5 py-0.5 font-mono">ESC</kbd>
        </div>

        <div className="max-h-[400px] overflow-y-auto custom-scrollbar">
          {query && !loading && results.length === 0 && (
            <div className="flex flex-col items-center py-12 text-outline/60">
              <span className="material-symbols-outlined text-[32px] mb-2">search_off</span>
              <span className="text-sm">{t("search.no_results")}</span>
            </div>
          )}

          {!query && (
            <div className="flex flex-col items-center py-12 text-outline/60">
              <span className="material-symbols-outlined text-[32px] mb-2">search</span>
              <span className="text-sm">{t("search.global_hint")}</span>
            </div>
          )}

          {results.length > 0 && (
            <div className="py-1">
              {results.map((r, i) => (
                <button
                  key={`${r.type}-${r.label}-${i}`}
                  onClick={r.onSelect}
                  onMouseEnter={() => setSelectedIdx(i)}
                  className={`w-full flex items-start gap-3 px-4 py-2.5 text-left transition-colors ${
                    i === selectedIdx ? "bg-surface-container" : "hover:bg-surface-container/50"
                  }`}
                >
                  <span className={`material-symbols-outlined text-[18px] mt-0.5 ${
                    r.type === "conversation" ? "text-primary-container" :
                    r.type === "document" ? "text-amber-400" : "text-violet-400"
                  }`}>
                    {r.icon}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] text-on-surface font-medium truncate">{r.label}</div>
                    <div className="text-[11px] text-outline truncate">{r.sublabel}</div>
                  </div>
                  <span className={`text-[9px] uppercase tracking-wider font-medium px-1.5 py-0.5 rounded shrink-0 mt-0.5 ${
                    r.type === "conversation" ? "bg-primary-container/10 text-primary-container" :
                    r.type === "document" ? "bg-amber-500/10 text-amber-400" : "bg-violet-500/10 text-violet-400"
                  }`}>
                    {r.type === "conversation" ? "Chat" : r.type === "document" ? "Doc" : "Memory"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center gap-4 px-4 py-2 border-t border-outline-variant/20 text-[10px] text-outline/50">
          <span className="flex items-center gap-1"><kbd className="text-[9px] border border-outline-variant/20 rounded px-1">↑↓</kbd> Navigate</span>
          <span className="flex items-center gap-1"><kbd className="text-[9px] border border-outline-variant/20 rounded px-1">↵</kbd> Open</span>
          <span className="flex items-center gap-1"><kbd className="text-[9px] border border-outline-variant/20 rounded px-1">ESC</kbd> Close</span>
        </div>
      </div>
    </div>
  );
}
