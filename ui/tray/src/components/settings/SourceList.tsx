import type { SyncSourceType } from "../../api/types";

export interface LocalSourceMeta {
  sync_count: number;
  last_sync_ok: boolean;
  last_error: string;
  added_at: number;
}

export type EnrichedSource = import("../../api/types").SyncSource & LocalSourceMeta;

export const SOURCE_TYPES: { id: SyncSourceType; label: string; hint: string }[] = [
  { id: "rss", label: "RSS/Atom", hint: "https://example.com/feed.xml" },
  { id: "github", label: "GitHub Repo", hint: "owner/repo or full URL" },
  { id: "web", label: "Web Page", hint: "https://example.com/article" },
  { id: "arxiv", label: "arXiv", hint: "AI, cs, math (tag-based search)" },
  { id: "youtube", label: "YouTube", hint: "https://youtube.com/watch?v=..." },
  { id: "pubmed", label: "PubMed", hint: "Search term (e.g. artificial intelligence)" },
];

export const TYPE_LABEL: Record<SyncSourceType, string> = {
  rss: "RSS",
  github: "GitHub",
  web: "Web",
  arxiv: "arXiv",
  youtube: "YouTube",
  pubmed: "PubMed",
};

interface SourceListProps {
  filtered: EnrichedSource[];
  syncing: string | null;
  backendOk: boolean | null;
  expandedId: string | null;
  onSyncOne: (id: string) => void;
  onRemove: (id: string) => void;
  onExpand: (id: string | null) => void;
  formatTime: (ts: number | null) => string;
  sources: EnrichedSource[];
  filter: SyncSourceType | "all";
  loading: boolean;
}

export default function SourceList({
  filtered,
  syncing,
  backendOk,
  expandedId,
  onSyncOne,
  onRemove,
  onExpand,
  formatTime,
  sources,
  filter,
  loading,
}: SourceListProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <span className="inline-block w-6 h-6 border-2 border-outline border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (filtered.length === 0 && sources.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center gap-3">
        <svg className="w-10 h-10 text-outline/20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
        <p className="text-[14px] font-medium text-outline/80">No links yet</p>
        <p className="text-[12px] text-outline/50 max-w-[300px]">
          Add RSS feeds, GitHub repos, or web pages. They're saved locally and will sync when the backend is available.
        </p>
      </div>
    );
  }

  if (filtered.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-center">
        <p className="text-[13px] text-outline/60">No {filter} sources</p>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <div className="text-[11px] text-outline font-semibold mb-2">
        {filtered.length} link{filtered.length !== 1 ? "s" : ""}
        {!backendOk && " (offline)"}
      </div>
      {filtered.map((source) => (
        <div key={source.id}>
          <div
            className="flex items-center justify-between p-3 rounded-[8px] bg-surface-container-low border border-outline-variant/50 group hover:border-outline-variant transition-colors cursor-pointer"
            onClick={() => onExpand(expandedId === source.id ? null : source.id)}
          >
            <div className="flex items-center gap-3 overflow-hidden min-w-0 flex-1">
              <div className="relative shrink-0">
                <div className={`w-3 h-3 rounded-full ${
                  syncing === source.id ? "bg-blue-400 animate-pulse" :
                  !source.last_sync_ok && source.sync_count > 0 ? "bg-error" :
                  source.sync_count === 0 ? "bg-outline/20" :
                  "bg-success-green"
                }`} title={
                  syncing === source.id ? "Syncing…" :
                  !source.last_sync_ok ? "Last sync failed" :
                  source.sync_count === 0 ? "Not synced yet" :
                  "Synced successfully"
                } />
              </div>
              <div className="overflow-hidden min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[14px] font-medium text-on-surface truncate">
                    {source.label || source.uri}
                  </span>
                  <span className="text-[9px] font-bold tracking-wide uppercase text-outline bg-surface-container px-1.5 py-0.5 rounded shrink-0">
                    {TYPE_LABEL[source.source_type] ?? source.source_type}
                  </span>
                  {!backendOk && (
                    <span className="text-[9px] text-outline/50 bg-outline/5 px-1.5 py-0.5 rounded shrink-0">
                      offline
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 text-[10px] text-outline mt-0.5 flex-wrap">
                  <span className="font-mono text-outline/60 truncate max-w-[200px]">{source.uri}</span>
                  <span className="text-outline/30">·</span>
                  <span>Syncs: <strong>{source.sync_count}</strong></span>
                  <span className="text-outline/30">·</span>
                  <span>Last: {formatTime(source.last_sync_at)}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-0.5 ml-2 shrink-0">
              <button
                onClick={(e) => { e.stopPropagation(); onSyncOne(source.id); }}
                disabled={syncing === source.id || !backendOk}
                className={`p-2 rounded-[6px] transition-colors ${
                  !backendOk
                    ? "text-outline/30 cursor-not-allowed"
                    : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
                }`}
                title={!backendOk ? "Start backend to sync" : "Sync now"}
              >
                {syncing === source.id ? (
                  <span className="inline-block w-4 h-4 border-2 border-outline border-t-transparent rounded-full animate-spin" />
                ) : (
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M21 12a9 9 0 11-9-9" />
                    <path d="M21 3v6h-6" />
                  </svg>
                )}
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onRemove(source.id); }}
                className="p-2 rounded-[6px] text-on-surface-variant hover:text-error hover:bg-surface-container transition-colors"
                title="Remove"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onExpand(expandedId === source.id ? null : source.id); }}
                className={`p-2 rounded-[6px] transition-colors ${
                  expandedId === source.id ? "text-primary-container" : "text-outline/40"
                }`}
                title={expandedId === source.id ? "Collapse" : "Expand"}
              >
                <svg
                  className={`w-4 h-4 transition-transform ${expandedId === source.id ? "rotate-180" : ""}`}
                  viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
                >
                  <path d="M6 9l6 6 6-6" />
                </svg>
              </button>
            </div>
          </div>

          {expandedId === source.id && (
            <div className="mx-3 p-3 bg-surface-container rounded-[8px] border border-outline-variant/30 text-[11px] space-y-2 -mt-0.5">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <span className="text-outline/60 block">URL</span>
                  <span className="text-on-surface font-mono break-all">{source.uri}</span>
                </div>
                <div>
                  <span className="text-outline/60 block">Interval / Cron</span>
                  <span className="text-on-surface">{source.schedule_cron || `${source.interval_minutes} min`}</span>
                </div>
                <div>
                  <span className="text-outline/60 block">Tags</span>
                  <span className="text-on-surface">{source.tags.length ? source.tags.join(", ") : "—"}</span>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 pt-1 border-t border-outline-variant/20">
                <div>
                  <span className="text-outline/60 block">Sync count</span>
                  <span className="text-on-surface font-semibold">{source.sync_count}</span>
                </div>
                <div>
                  <span className="text-outline/60 block">Items indexed</span>
                  <span className="text-on-surface font-semibold">{source.items_indexed}</span>
                </div>
                <div>
                  <span className="text-outline/60 block">Added</span>
                  <span className="text-on-surface">{formatTime(source.added_at / 1000)}</span>
                </div>
              </div>
              {source.last_error && (
                <div className="pt-1 border-t border-outline-variant/20">
                  <span className="text-error/80">Last error: {source.last_error}</span>
                </div>
              )}
              {!backendOk && (
                <div className="pt-1 border-t border-outline-variant/20">
                  <span className="text-outline/60">Connect the backend to sync content from this source.</span>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
