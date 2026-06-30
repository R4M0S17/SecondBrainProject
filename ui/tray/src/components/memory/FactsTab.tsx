import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMemoryStore, type MemoryFilter } from "../../stores/memory";
import type { MemoryEpisode } from "../../api/types";
import MemoryEpisodeCard from "./MemoryEpisodeCard";
import MemoryEpisodeEditor from "./MemoryEpisodeEditor";

interface FactsTabProps {
  compact?: boolean;
}

export default function FactsTab({ compact: _compact = false }: FactsTabProps) {
  const { t } = useTranslation();
  const {
    episodes,
    stats,
    loading,
    addEpisode,
    updateEpisode,
    deleteEpisode,
    togglePin,
    highlightedId,
  } = useMemoryStore();

  const [filter, setFilter] = useState<MemoryFilter>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newContent, setNewContent] = useState("");
  const [editingEpisode, setEditingEpisode] = useState<MemoryEpisode | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [textSearch, setTextSearch] = useState("");

  const pinnedCount = useMemo(() => episodes.filter((e) => e.pinned).length, [episodes]);

  const sourceDist = useMemo(() => {
    const counts: Record<string, number> = { episode: 0, consolidation: 0, archived: 0, manual: 0 };
    for (const ep of episodes) {
      counts[ep.source] = (counts[ep.source] ?? 0) + 1;
    }
    return counts;
  }, [episodes]);

  const BASE_FILTERS: MemoryFilter[] = ["all", "pinned"];
  const EXCLUDED_FROM_DYNAMIC = new Set(["manual", "pinned"]);

  const dynamicFilters = useMemo(() => {
    const tagCounts = new Map<string, number>();
    for (const ep of episodes) {
      for (const tag of ep.tags) {
        if (!EXCLUDED_FROM_DYNAMIC.has(tag)) {
          tagCounts.set(tag, (tagCounts.get(tag) ?? 0) + 1);
        }
      }
    }
    return Array.from(tagCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([tag]) => tag);
  }, [episodes]);

  const allFilters = [...BASE_FILTERS, ...dynamicFilters];

  const filteredEpisodes = useMemo(() => {
    let list = [...episodes];
    if (filter === "pinned") list = list.filter((e) => e.pinned);
    else if (filter !== "all") list = list.filter((e) => e.tags.includes(filter));
    if (textSearch.trim()) {
      const q = textSearch.toLowerCase();
      list = list.filter(
        (e) =>
          e.content.toLowerCase().includes(q) ||
          e.tags.some((t) => t.toLowerCase().includes(q))
      );
    }
    list.sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
      return b.created_at - a.created_at;
    });
    return list;
  }, [episodes, filter, textSearch]);


  const handleAdd = async () => {
    const text = newContent.trim();
    if (!text) return;
    try {
      await addEpisode(text);
      setNewContent("");
      setShowAddForm(false);
    } catch {
      /* store error */
    }
  };

  const handleExport = () => {
    const exportData = episodes.map((ep) => ({
      content: ep.content,
      tags: ep.tags,
      source: ep.source,
      pinned: ep.pinned,
      confidence: ep.confidence,
      created_at: new Date(ep.created_at).toISOString(),
    }));
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cerebro-memory-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exampleChips = [
    { label: t("memory.empty_example_label_1"), text: t("memory.empty_example_text_1") },
    { label: t("memory.empty_example_label_2"), text: t("memory.empty_example_text_2") },
    { label: t("memory.empty_example_label_3"), text: t("memory.empty_example_text_3") },
  ];

  return (
    <section className="bg-surface-container-low/30 border border-outline-variant/10 rounded-xl p-4 md:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-[15px] font-semibold text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-[20px] text-violet-400">bookmark</span>
            {t("memory.saved_title")}
          </h2>
          <p className="text-[11px] text-on-surface-variant/70 mt-1 max-w-xl">
            {t("memory.saved_desc")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {episodes.length > 0 && (
            <button
              type="button"
              onClick={handleExport}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container text-on-surface-variant text-[12px] hover:opacity-90 shrink-0 border border-outline-variant/20"
              title={t("memory.export_title")}
            >
              <span className="material-symbols-outlined text-[16px]">download</span>
              {t("memory.export")}
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowAddForm((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-container text-on-primary text-[12px] font-medium hover:opacity-90 shrink-0"
          >
            <span className="material-symbols-outlined text-[16px]">add</span>
            {t("memory.add_episode")}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2 mb-4">
        {[
          { icon: "neurology", label: t("memory.stat_stored"), value: stats.episodes_stored, tip: "Total saved facts" },
          { icon: "push_pin", label: t("memory.stat_pinned"), value: pinnedCount, tip: "Pinned facts" },
          { icon: "history", label: t("memory.stat_recalls"), value: stats.recall_hits_session, tip: "Times Cerebro used memory in this session" },
          { icon: "data_usage", label: t("memory.stat_context"), value: `${stats.context_memory_pct}%`, tip: "Memory currently active in agent context" },
        ].map((item) => (
          <div key={item.label} className="bg-surface-container/60 rounded-lg px-2 py-2 text-center" title={item.tip}>
            <span className="material-symbols-outlined text-[16px] text-violet-400/70 block mb-0.5">{item.icon}</span>
            <p className="text-[15px] font-bold text-on-surface">{item.value}</p>
            <p className="text-[9px] text-on-surface-variant/60 uppercase tracking-wide">{item.label}</p>
          </div>
        ))}
      </div>

      {episodes.length >= 5 && (
        <div className="mb-3 flex items-center gap-1 h-1.5 rounded-full overflow-hidden" title="Memory source distribution">
          {Object.entries(sourceDist).map(([source, count]) => {
            const pct = Math.round((count / episodes.length) * 100);
            if (pct === 0) return null;
            const colors: Record<string, string> = {
              manual: "bg-violet-400/70",
              episode: "bg-blue-400/70",
              consolidation: "bg-green-400/70",
              archived: "bg-outline/40",
            };
            return (
              <div
                key={source}
                className={`h-full ${colors[source] ?? "bg-outline/40"}`}
                style={{ width: `${pct}%` }}
                title={`${source}: ${count}`}
              />
            );
          })}
        </div>
      )}

      {showAddForm && (
        <div className="mb-4 bg-surface-container border border-primary-container/20 rounded-xl p-3 space-y-2">
          <textarea
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            rows={3}
            placeholder={t("memory.add_placeholder")}
            className="w-full bg-surface-container-low border border-outline-variant/20 rounded-lg px-3 py-2 text-[12px] text-on-surface resize-none focus:outline-none focus:border-primary-container/50"
          />
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => { setShowAddForm(false); setNewContent(""); }} className="px-3 py-1.5 text-[11px] text-on-surface-variant">
              {t("note.cancel")}
            </button>
            <button type="button" onClick={() => void handleAdd()} disabled={!newContent.trim()} className="px-3 py-1.5 rounded-lg bg-primary-container text-on-primary text-[11px] font-medium disabled:opacity-40">
              {t("memory.save_episode")}
            </button>
          </div>
        </div>
      )}

      {episodes.length >= 5 && (
        <div className="relative mb-2">
          <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-[14px] text-outline">search</span>
          <input
            type="text"
            value={textSearch}
            onChange={(e) => setTextSearch(e.target.value)}
            placeholder={t("memory.search_placeholder")}
            className="w-full bg-surface-container-low border border-outline-variant/20 rounded-lg pl-8 pr-3 py-1.5 text-[12px] text-on-surface placeholder:text-outline/50 focus:outline-none focus:border-primary-container/50"
          />
          {textSearch && (
            <button
              type="button"
              onClick={() => setTextSearch("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-outline hover:text-on-surface"
            >
              <span className="material-symbols-outlined text-[14px]">close</span>
            </button>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-1.5 mb-3">
        {allFilters.map((f) => {
          const count = f === "all"
            ? episodes.length
            : f === "pinned"
            ? episodes.filter((e) => e.pinned).length
            : episodes.filter((e) => e.tags.includes(f)).length;
          return (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={`px-2.5 py-1 rounded-full text-[10px] font-medium transition-colors flex items-center gap-1 ${
                filter === f
                  ? "bg-violet-400/20 text-violet-300 border border-violet-400/30"
                  : "bg-surface-container text-on-surface-variant border border-transparent hover:border-outline-variant/20"
              }`}
            >
              {f === "all" ? t("memory.filter_all")
               : f === "pinned" ? t("memory.filter_pinned")
               : f}
              <span className="opacity-60">{count}</span>
            </button>
          );
        })}
          {stats.recall_hits_session > 0 && (
          <span className="flex items-center gap-1 text-[10px] text-violet-400/70 font-label-mono ml-auto self-center" title="Times Cerebro retrieved memory from LanceDB in this session">
            <span className="material-symbols-outlined text-[12px]">neurology</span>
            {t("memory.recall_hits_count", { count: stats.recall_hits_session })}
          </span>
        )}
      </div>

      {loading ? (
        <p className="text-[12px] text-outline text-center py-8">{t("status.loading")}</p>
      ) : filteredEpisodes.length === 0 ? (
        <div className="text-center py-10 space-y-4 border border-dashed border-outline-variant/20 rounded-xl">
          <span className="material-symbols-outlined text-[36px] text-outline/40">neurology</span>
          <p className="text-[13px] text-on-surface-variant px-4 max-w-sm mx-auto">{t("memory.empty_hint")}</p>
          <div className="flex flex-wrap justify-center gap-2 px-4">
            {exampleChips.map((ex) => (
              <button
                key={ex.label}
                type="button"
                onClick={() => { setNewContent(ex.text); setShowAddForm(true); }}
                className="px-3 py-1.5 rounded-full text-[11px] bg-surface-container text-on-surface-variant border border-outline-variant/20 hover:border-primary-container/40 hover:text-primary-container transition-colors"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-2">
           {filteredEpisodes.map((episode) => (
            <MemoryEpisodeCard
              key={episode.id}
              episode={episode}
              expanded={expandedId === episode.id}
              onToggleExpand={() => setExpandedId((id) => (id === episode.id ? null : episode.id))}
              onEdit={() => setEditingEpisode(episode)}
               onDelete={() => setDeleteConfirmId(episode.id)}
              onTogglePin={() => void togglePin(episode.id)}
              highlighted={highlightedId === episode.id}
            />
          ))}
        </div>
      )}

      {editingEpisode && (
        <MemoryEpisodeEditor
          episode={editingEpisode}
          onClose={() => setEditingEpisode(null)}
          onSave={async (content, tags) => {
            await updateEpisode(editingEpisode.id, content, tags);
            setEditingEpisode(null);
          }}
        />
      )}

      {deleteConfirmId && (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/60"
          role="dialog"
          aria-modal="true"
          onClick={() => setDeleteConfirmId(null)}
        >
          <div
            className="w-full max-w-sm bg-surface-container border border-outline-variant rounded-xl shadow-xl p-5 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-[24px] text-error">warning</span>
              <h3 className="text-[14px] font-semibold text-on-surface">
                {t("memory.delete_confirm_title")}
              </h3>
            </div>
            <p className="text-[12px] text-on-surface-variant leading-[17px]">
              {t("memory.delete_confirm_desc")}
            </p>
            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => setDeleteConfirmId(null)}
                className="px-3 py-1.5 text-[12px] text-on-surface-variant hover:text-on-surface transition-colors"
              >
                {t("note.cancel")}
              </button>
              <button
                type="button"
                onClick={() => {
                  void deleteEpisode(deleteConfirmId);
                  setDeleteConfirmId(null);
                }}
                className="px-4 py-1.5 rounded-lg bg-error text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
              >
                {t("memory.delete_confirm_action")}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
