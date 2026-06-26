import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useHistoryStore } from "../../stores/history";
import HistoryDetail from "./HistoryDetail";
import type { ConversationSummary } from "../../api/types";

function formatDateLabel(dateStr: string, t: (key: string) => string): string {
  const d = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (d >= today) return t("history.today");
  if (d >= yesterday) return t("history.yesterday");

  const weekStart = new Date(today);
  weekStart.setDate(weekStart.getDate() - weekStart.getDay());
  if (d >= weekStart) return t("history.this_week");

  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function formatRelativeTime(dateStr: string): string {
  const d = new Date(dateStr);
  const now = Date.now();
  const diffMs = now - d.getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export default function HistoryTab() {
  const { t } = useTranslation();
  const {
    conversations,
    loading,
    query,
    tab,
    error,
    selectedIds,
    refresh,
    search,
    select,
    remove,
    back,
    toggleSelect,
    selectAll,
    clearSelection,
    batchDelete,
    batchPin,
  } = useHistoryStore();

  const [searchInput, setSearchInput] = useState(query);
  const [selecting, setSelecting] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void search(searchInput);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [searchInput, search]);

  const allSelected = conversations.length > 0 && selectedIds.size === conversations.length;

  if (tab === "detail") {
    return <HistoryDetail onBack={back} onDelete={remove} />;
  }

  const groups = groupByDate(conversations, t);

  return (
    <section className="bg-surface-container-low/20 border border-outline-variant/10 rounded-xl p-4 md:p-5">
      <div className="mb-3">
        <h2 className="text-[14px] font-semibold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px] text-outline">history</span>
          {t("history.title")}
        </h2>
        <p className="text-[11px] text-on-surface-variant/60 mt-1">{t("history.desc")}</p>
      </div>

      {/* Search */}
      <div className="relative mb-3">
        <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-[14px] text-outline">search</span>
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder={t("history.search_placeholder")}
          className="w-full bg-surface-container-low border border-outline-variant/20 rounded-lg pl-8 pr-3 py-2 text-[12px] text-on-surface placeholder:text-outline/50 focus:outline-none focus:border-primary-container/50"
        />
      </div>

      {error && (
        <p className="text-[11px] text-error mb-3">{error}</p>
      )}

      {/* Toolbar: select toggle + select all + count + cancel */}
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => {
              if (selecting) {
                clearSelection();
                setSelecting(false);
              } else {
                setSelecting(true);
              }
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-medium transition-all ${
              selecting
                ? "bg-blue-500/15 text-blue-400 ring-1 ring-inset ring-blue-400/30"
                : "bg-surface-container/40 text-on-surface-variant/70 hover:text-on-surface-variant hover:bg-surface-container/60"
            }`}
          >
            <span className="material-symbols-outlined text-[14px]">
              {selecting ? "close" : "checklist"}
            </span>
            {selecting ? t("history.done") : t("history.select")}
          </button>

          {selecting && (
            <>
              <button
                type="button"
                onClick={allSelected ? clearSelection : selectAll}
                className="flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 transition-colors"
              >
                <span className="material-symbols-outlined text-[14px]">
                  {allSelected ? "deselect" : "select_all"}
                </span>
                {allSelected ? t("history.deselect_all") : t("history.select_all")}
              </button>
              {selectedIds.size > 0 && (
                <span className="text-[10px] text-outline">
                  {selectedIds.size} {t("history.selected")}
                </span>
              )}
            </>
          )}
        </div>
      </div>

      {loading && (
        <p className="text-[12px] text-outline text-center py-8">{t("status.loading")}</p>
      )}

      {!loading && conversations.length === 0 && (
        <p className="text-[12px] text-outline py-6 text-center">
          {searchInput ? t("history.no_results") : t("history.empty")}
        </p>
      )}

      {!loading && conversations.length > 0 && (
        <div className="space-y-4 max-h-[340px] overflow-y-auto custom-scrollbar">
          {groups.map(([label, items]) => (
            <div key={label}>
              <p className="text-[10px] uppercase tracking-wider text-on-surface-variant/50 mb-1.5 px-0.5">
                {label}
              </p>
              <div className="space-y-1">
                {items.map((conv) => {
                  const isChecked = selectedIds.has(conv.conv_id);
                  return (
                    <div
                      key={conv.conv_id}
                      onClick={() => {
                        if (selecting) {
                          toggleSelect(conv.conv_id);
                        } else {
                          void select(conv.conv_id);
                        }
                      }}
                      className={`flex items-center gap-2 rounded-lg py-2.5 pr-2.5 transition-all cursor-pointer ${
                        selecting
                          ? isChecked
                            ? "bg-blue-500/8 ring-1 ring-inset ring-blue-400/40 pl-2"
                            : "bg-surface-container/25 pl-2"
                          : "bg-surface-container/40 hover:bg-surface-container/70 pl-2.5"
                      }`}
                    >
                      {selecting && (
                        <div
                          className={`shrink-0 w-4 h-4 rounded-full flex items-center justify-center transition-all ${
                            isChecked
                              ? "bg-blue-500 ring-2 ring-blue-400/30"
                              : "ring-1 ring-inset ring-outline/40"
                          }`}
                        >
                          {isChecked && (
                            <span className="material-symbols-outlined text-[10px] text-white font-bold">check</span>
                          )}
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-[12px] text-on-surface font-medium truncate flex items-center gap-1">
                            {conv.pinned && (
                              <span className="material-symbols-outlined text-[12px] text-violet-400 shrink-0">push_pin</span>
                            )}
                            {conv.first_user_message || t("history.untitled")}
                          </span>
                          <span className="shrink-0 text-[10px] text-outline">
                            {conv.message_count}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[10px] text-outline">
                            {formatRelativeTime(conv.last_active)}
                          </span>
                          <span className="text-[10px] text-outline">&middot;</span>
                          <span className="text-[10px] text-outline">
                            {conv.message_count} {t("history.messages")}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Batch actions */}
      {selecting && selectedIds.size > 0 && (
        <div className="flex items-center gap-2 mt-4 pt-3 border-t border-outline-variant/10">
          <button
            type="button"
            onClick={() => void batchPin(true)}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-500/10 text-blue-400 text-[11px] font-medium hover:bg-blue-500/20 transition-colors"
          >
            <span className="material-symbols-outlined text-[14px]">push_pin</span>
            {t("history.pin_selected")}
          </button>
          <button
            type="button"
            onClick={() => void batchPin(false)}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface-container/40 text-on-surface-variant text-[11px] font-medium hover:bg-surface-container/60 transition-colors"
          >
            <span className="material-symbols-outlined text-[14px]">push_pin</span>
            {t("history.unpin_selected")}
          </button>
          <button
            type="button"
            onClick={() => void batchDelete()}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-error/15 text-error text-[11px] font-medium hover:bg-error/25 transition-colors ml-auto"
          >
            <span className="material-symbols-outlined text-[14px]">delete</span>
            {t("history.delete_selected")}
          </button>
        </div>
      )}
    </section>
  );
}

function groupByDate(convs: ConversationSummary[], t: (key: string) => string): [string, ConversationSummary[]][] {
  const groups = new Map<string, ConversationSummary[]>();
  for (const conv of convs) {
    const label = formatDateLabel(conv.last_active || conv.started_at, t);
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label)!.push(conv);
  }
  return Array.from(groups.entries());
}
