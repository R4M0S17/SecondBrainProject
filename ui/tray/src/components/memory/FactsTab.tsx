import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMemoryStore, type MemoryFilter } from "../../stores/memory";
import type { MemoryEpisode } from "../../api/types";
import MemoryEpisodeCard from "./MemoryEpisodeCard";
import MemoryEpisodeEditor from "./MemoryEpisodeEditor";

const FILTERS: MemoryFilter[] = ["all", "pinned", "session", "academic", "code"];

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
  } = useMemoryStore();

  const [filter, setFilter] = useState<MemoryFilter>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newContent, setNewContent] = useState("");
  const [editingEpisode, setEditingEpisode] = useState<MemoryEpisode | null>(null);

  const pinnedCount = useMemo(() => episodes.filter((e) => e.pinned).length, [episodes]);

  const filteredEpisodes = useMemo(() => {
    let list = [...episodes];
    if (filter === "pinned") list = list.filter((e) => e.pinned);
    else if (filter !== "all") list = list.filter((e) => e.tags.includes(filter));
    list.sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
      return b.created_at - a.created_at;
    });
    return list;
  }, [episodes, filter]);

  const recallRate =
    stats.queries_with_recall > 0
      ? Math.round((stats.recall_hits_session / stats.queries_with_recall) * 100)
      : 0;

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
        <button
          type="button"
          onClick={() => setShowAddForm((v) => !v)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-container text-on-primary text-[12px] font-medium hover:opacity-90 shrink-0"
        >
          <span className="material-symbols-outlined text-[16px]">add</span>
          {t("memory.add_episode")}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-4">
        {[
          { icon: "neurology", label: t("memory.stat_stored"), value: stats.episodes_stored, tip: "Total saved facts" },
          { icon: "push_pin", label: t("memory.stat_pinned"), value: pinnedCount, tip: "Pinned facts" },
          { icon: "history", label: t("memory.stat_recalls"), value: stats.recall_hits_session, tip: "Times Cerebro used memory in this session" },
        ].map((item) => (
          <div key={item.label} className="bg-surface-container/60 rounded-lg px-2 py-2 text-center" title={item.tip}>
            <span className="material-symbols-outlined text-[16px] text-violet-400/70 block mb-0.5">{item.icon}</span>
            <p className="text-[15px] font-bold text-on-surface">{item.value}</p>
            <p className="text-[9px] text-on-surface-variant/60 uppercase tracking-wide">{item.label}</p>
          </div>
        ))}
      </div>

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

      <div className="flex flex-wrap gap-1.5 mb-3">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`px-2.5 py-1 rounded-full text-[10px] font-medium transition-colors ${
              filter === f
                ? "bg-violet-400/20 text-violet-300 border border-violet-400/30"
                : "bg-surface-container text-on-surface-variant border border-transparent hover:border-outline-variant/20"
            }`}
          >
            {t(`memory.filter_${f}`)}
          </button>
        ))}
            {recallRate > 0 && (
          <span className="text-[10px] text-outline font-label-mono ml-auto self-center">
            {t("memory.recall_rate", { rate: recallRate })}
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
              onDelete={() => void deleteEpisode(episode.id)}
              onTogglePin={() => void togglePin(episode.id)}
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
    </section>
  );
}
