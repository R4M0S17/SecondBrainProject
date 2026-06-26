import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { MemoryRecallResult } from "../../api/types";

interface MemoryRecallSearchProps {
  onSearch: (query: string) => Promise<MemoryRecallResult[]>;
  usingMock?: boolean;
}

export default function MemoryRecallSearch({ onSearch, usingMock = false }: MemoryRecallSearchProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MemoryRecallResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) {
      setResults(null);
      setSearchError(null);
      return;
    }
    setSearching(true);
    setSearchError(null);
    try {
      const hits = await onSearch(q);
      setResults(hits);
    } catch (err) {
      setResults([]);
      setSearchError(err instanceof Error ? err.message : t("memory.recall_error"));
    } finally {
      setSearching(false);
    }
  };

  return (
    <section>
      <label className="block text-label-caps text-outline tracking-wider mb-2">
        {t("memory.recall_test")}
      </label>
      <p className="text-[11px] text-on-surface-variant/60 mb-2 leading-[15px]">
        {t("memory.recall_test_hint")}
      </p>
      <form onSubmit={(e) => void handleSubmit(e)} className="flex gap-2">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("memory.recall_placeholder")}
          className="flex-1 min-w-0 bg-surface-container-low border border-outline-variant/20 rounded-lg px-3 py-2 text-[12px] text-on-surface placeholder:text-outline/50 focus:outline-none focus:border-primary-container/50"
        />
        <button
          type="submit"
          disabled={searching}
          className="px-3 py-2 rounded-lg bg-primary-container/15 text-primary-container text-[12px] font-medium hover:bg-primary-container/25 transition-colors shrink-0 disabled:opacity-50"
        >
          {searching ? t("status.loading") : t("memory.recall_run")}
        </button>
      </form>

      {searchError && (
        <p className="text-[11px] text-error mt-2">{searchError}</p>
      )}

      {results !== null && (
        <div className="mt-3 space-y-2">
          {results.length === 0 ? (
            <p className="text-[11px] text-outline py-2">{t("memory.recall_empty")}</p>
          ) : (
            results.map(({ episode, relevance_score }) => (
              <div
                key={episode.id}
                className="bg-surface-container-low/40 border border-outline-variant/10 rounded-lg p-2.5"
              >
                <p className="text-[11px] text-on-surface-variant line-clamp-2 leading-[15px]">
                  {episode.content}
                </p>
                <div className="flex items-center gap-2 mt-1.5">
                  <div className="flex-1 h-[2px] bg-surface-container rounded-full overflow-hidden">
                    <div
                      className="h-full bg-violet-400/70 rounded-full"
                      style={{ width: `${Math.round(relevance_score * 100)}%` }}
                    />
                  </div>
                  <span className="font-mono text-[10px] text-on-surface-variant">
                    {relevance_score.toFixed(2)}
                  </span>
                </div>
              </div>
            ))
          )}
          {usingMock && (
            <p className="text-[10px] text-outline/60 italic">{t("memory.recall_mock_notice")}</p>
          )}
        </div>
      )}
    </section>
  );
}
