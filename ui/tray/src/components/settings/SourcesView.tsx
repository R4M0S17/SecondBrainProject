import { useCallback, useEffect, useRef, useState } from "react";
import {
  listSyncSources,
  addSyncSource as apiAddSource,
  exportSyncSources,
  importSyncSources as apiImportSources,
  removeSyncSource as apiRemoveSource,
  triggerSync,
  triggerSyncStream,
} from "../../api/client";
import type { SyncSource, SyncSourceType } from "../../api/types";

// ── Types ──

interface LocalSourceMeta {
  sync_count: number;
  last_sync_ok: boolean;
  last_error: string;
  added_at: number;
}

type EnrichedSource = SyncSource & LocalSourceMeta;

// ── Constants ──

const SOURCE_TYPES: { id: SyncSourceType; label: string; hint: string }[] = [
  { id: "rss", label: "RSS/Atom", hint: "https://example.com/feed.xml" },
  { id: "github", label: "GitHub Repo", hint: "owner/repo or full URL" },
  { id: "web", label: "Web Page", hint: "https://example.com/article" },
  { id: "arxiv", label: "arXiv", hint: "AI, cs, math (tag-based search)" },
  { id: "youtube", label: "YouTube", hint: "https://youtube.com/watch?v=..." },
  { id: "pubmed", label: "PubMed", hint: "Search term (e.g. artificial intelligence)" },
];

const TYPE_LABEL: Record<SyncSourceType, string> = {
  rss: "RSS",
  github: "GitHub",
  web: "Web",
  arxiv: "arXiv",
  youtube: "YouTube",
  pubmed: "PubMed",
};

const STORAGE_KEY = "cerebro_ks_sources";

const DEFAULT_FORM = {
  source_type: "rss" as SyncSourceType,
  uri: "",
  label: "",
  interval_minutes: 60,
  tags: "",
  schedule_cron: "",
};

// ── LocalStorage helpers ──

function loadLocal(): EnrichedSource[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function saveLocal(sources: EnrichedSource[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(sources)); } catch {}
}

// ── Component ──

export default function SourcesView() {
  const [sources, setSources] = useState<EnrichedSource[]>(loadLocal);
  const [loading, setLoading] = useState(true);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<SyncSourceType | "all">("all");
  const [statusMessage, setStatusMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const showMessage = (text: string, ok: boolean) => {
    setStatusMessage({ text, ok });
    setTimeout(() => setStatusMessage(null), 4000);
  };

  // ── Try to reach backend ──
  const tryBackend = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listSyncSources();
      setBackendOk(true);
      // Push any local-only sources to backend
      const local = loadLocal();
      const backendIds = new Set(data.map((s) => s.id));
      const localOnly = local.filter((s) => !backendIds.has(s.id));
      for (const s of localOnly) {
        try { await apiAddSource(s); } catch {}
      }
      // Merge: backend data enriched with local metadata
      const localMap = new Map(local.map((s) => [s.id, s]));
      const merged: EnrichedSource[] = data.map((s) => ({
        ...s,
        sync_count: localMap.get(s.id)?.sync_count ?? 0,
        last_sync_ok: !s.last_error,
        last_error: s.last_error || "",
        added_at: localMap.get(s.id)?.added_at ?? Date.now(),
      }));
      const allSources = [...merged, ...localOnly.map((s) => ({...s, added_at: s.added_at ?? Date.now()}))];
      setSources(allSources);
      saveLocal(allSources);
      if (localOnly.length > 0) {
        showMessage(`Synced ${localOnly.length} local source(s) to backend`, true);
      }
    } catch {
      setBackendOk(false);
      const cached = loadLocal();
      if (cached.length > 0) setSources(cached);
      // Retry in 5s
      setTimeout(() => void tryBackend(), 5000);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void tryBackend(); }, [tryBackend]);

  // Listen for header sync button completing
  useEffect(() => {
    const handler = () => {
      if (backendOk !== false) { void tryBackend(); }
    };
    window.addEventListener("knowledge-sync-complete", handler);
    return () => window.removeEventListener("knowledge-sync-complete", handler);
  }, [tryBackend, backendOk]);

  // ── CRUD (all local-first) ──

  const updateSources = (fn: (prev: EnrichedSource[]) => EnrichedSource[]) => {
    setSources((prev) => {
      const next = fn(prev);
      saveLocal(next);
      return next;
    });
  };

  const handleAddSource = () => {
    setFormError(null);
    if (!form.uri.trim()) { setFormError("URL is required"); return; }

    const now = Date.now();
    const id = `src:${now}`;
    const entry: EnrichedSource = {
      id,
      source_type: form.source_type,
      uri: form.uri.trim(),
      label: form.label.trim() || form.uri.trim(),
      enabled: true,
      interval_minutes: form.interval_minutes,
      max_items_per_sync: 20,
      filter_min_relevance: 0.3,
      tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
      schedule_cron: form.schedule_cron.trim(),
      status: "idle",
      last_sync_at: 0,
      last_error: "",
      items_indexed: 0,
      sync_count: 0,
      last_sync_ok: true,
      added_at: now,
    };

    updateSources((prev) => [entry, ...prev]);
    setShowForm(false);
    setForm(DEFAULT_FORM);

    // Try to push to backend if available
    if (backendOk) {
      apiAddSource(entry).catch(() => {
        showMessage("Saved locally — backend will sync when available", false);
      });
    } else {
      showMessage("Saved locally — connect backend to enable sync", false);
    }
  };

  const handleRemove = (id: string) => {
    updateSources((prev) => prev.filter((s) => s.id !== id));
    if (backendOk) {
      apiRemoveSource(id).catch(() => {});
    }
  };

  // ── Sync actions (backend required) ──

  const handleSyncAll = async () => {
    if (!backendOk) { showMessage("Backend is offline — start the server to sync", false); return; }
    setSyncing("*");
    try {
      const completedSources = new Set<string>();
      await triggerSyncStream(
        { force: true },
        () => {},
        (complete) => {
          completedSources.add(complete.source_id);
          updateSources((prev) =>
            prev.map((s) =>
              s.id === complete.source_id ? {
                ...s,
                items_indexed: complete.indexed ?? s.items_indexed,
                last_sync_ok: complete.errors.length === 0,
                last_error: complete.errors.join("; "),
                last_sync_at: Date.now() / 1000,
                status: "idle" as const,
              } : s
            )
          );
        }
      );
      // Increment sync_count for all sources that completed
      updateSources((prev) =>
        prev.map((s) =>
          completedSources.has(s.id) ? { ...s, sync_count: s.sync_count + 1 } : s
        )
      );
      showMessage(`Synced ${completedSources.size} source(s)`, true);
    } catch {
      showMessage("Sync failed — try again", false);
    } finally {
      setSyncing(null);
    }
  };

  const handleExport = async () => {
    if (!backendOk) { showMessage("Backend is offline", false); return; }
    try {
      const data = await exportSyncSources();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cerebro-sources-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showMessage("Exported successfully", true);
    } catch {
      showMessage("Export failed", false);
    }
  };

  const handleImport = async () => {
    if (!backendOk) { showMessage("Backend is offline", false); return; }
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json";
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      try {
        const text = await file.text();
        const data = JSON.parse(text);
        const result = await apiImportSources(data);
        showMessage(`Imported ${result.added} source(s)${result.errors.length ? ` (${result.errors.length} errors)` : ""}`, result.errors.length === 0);
        await tryBackend();
      } catch {
        showMessage("Import failed — invalid file", false);
      }
    };
    input.click();
  };

  const handleSyncOne = async (id: string) => {
    if (!backendOk) { showMessage("Backend is offline", false); return; }
    setSyncing(id);
    try {
      const result = await triggerSyncStream(
        { source_id: id, force: true },
        () => {},
        (complete) => {
          updateSources((prev) =>
            prev.map((s) =>
              s.id === id ? {
                ...s,
                sync_count: s.sync_count + 1,
                items_indexed: complete.indexed ?? s.items_indexed,
                last_sync_ok: complete.errors.length === 0,
                last_error: complete.errors.join("; "),
                last_sync_at: Date.now() / 1000,
                status: "idle" as const,
              } : s
            )
          );
          const msg = complete.indexed > 0 ? `Synced: ${complete.indexed} items` : "Synced (0 new items)";
          showMessage(msg, true);
        }
      );
    } catch {
      updateSources((prev) =>
        prev.map((s) =>
          s.id === id ? { ...s, last_sync_ok: false, last_error: "Sync failed", status: "error" as const } : s
        )
      );
      showMessage(`Sync failed for ${id}`, false);
    } finally {
      setSyncing(null);
    }
  };

  // ── Helpers ──

  const formatTime = (ts: number | null) => {
    if (!ts || ts === 0) return "never";
    const d = new Date(ts * 1000);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 60000) return "just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return d.toLocaleDateString();
  };

  const filtered = filter === "all" ? sources : sources.filter((s) => s.source_type === filter);

  // ── Render ──

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 pt-5 pb-3 shrink-0">
        <div>
          <h1 className="text-[20px] font-bold text-on-surface">Knowledge Sources</h1>
          <p className="text-[11px] text-outline mt-0.5">
            Add links to RSS feeds, GitHub repos, or web pages
          </p>
        </div>
        {/* Backend indicator */}
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${
          backendOk === null ? "text-outline" :
          backendOk ? "text-success-green bg-success-green/10" :
          "text-error bg-error/10"
        }`}>
          <div className={`w-2 h-2 rounded-full ${
            backendOk === null ? "bg-outline/50 animate-pulse" :
            backendOk ? "bg-success-green" : "bg-error"
          }`} />
          {backendOk === null ? "Connecting…" : backendOk ? "Connected" : "Offline"}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 pb-6 custom-scrollbar">

        {/* Status message */}
        {statusMessage && (
          <div className={`flex items-center gap-2 p-3 mb-4 rounded-[8px] text-[12px] font-medium ${
            statusMessage.ok ? "bg-success-green/10 text-success-green" : "bg-error/10 text-error"
          }`}>
            {statusMessage.ok ? (
              <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                <path d="M20 6L9 17l-5-5" />
              </svg>
            ) : (
              <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4M12 16h.01" />
              </svg>
            )}
            {statusMessage.text}
            <button onClick={() => setStatusMessage(null)} className="ml-auto opacity-60 hover:opacity-100">
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Toolbar: Add + Filter + Sync */}
        <div className="flex flex-wrap gap-2 mb-5">
          <button
            onClick={() => { setShowForm(!showForm); setFormError(null); }}
            className="flex items-center gap-1.5 px-4 py-2 rounded-[8px] text-[13px] font-semibold bg-primary-container text-on-surface hover:opacity-90 transition-opacity"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M12 5v14M5 12h14" />
            </svg>
            Add Link
          </button>

          <div className="flex gap-1 bg-surface-container-low rounded-[8px] p-0.5 border border-outline-variant/50">
            {(["all", "rss", "github", "web", "arxiv", "youtube", "pubmed"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-[6px] text-[11px] font-semibold transition-colors ${
                  filter === f
                    ? "bg-surface-container text-on-surface"
                    : "text-outline hover:text-on-surface"
                }`}
              >
                {f === "all" ? "All" : TYPE_LABEL[f] || f}
              </button>
            ))}
          </div>

          <button
            onClick={() => void handleExport()}
            disabled={!backendOk}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-[8px] text-[12px] font-semibold transition-opacity ${
              backendOk
                ? "bg-surface-container-low border border-outline-variant text-outline hover:text-on-surface hover:bg-surface-container"
                : "bg-surface-container-low border border-outline-variant/30 text-outline/30 cursor-not-allowed"
            }`}
            title="Export sources"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
            </svg>
            Export
          </button>
          <button
            onClick={() => void handleImport()}
            disabled={!backendOk}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-[8px] text-[12px] font-semibold transition-opacity ${
              backendOk
                ? "bg-surface-container-low border border-outline-variant text-outline hover:text-on-surface hover:bg-surface-container"
                : "bg-surface-container-low border border-outline-variant/30 text-outline/30 cursor-not-allowed"
            }`}
            title="Import sources"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
            </svg>
            Import
          </button>

          <div className="flex-1" />

          <button
            onClick={() => void handleSyncAll()}
            disabled={syncing === "*" || !backendOk}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-[8px] text-[13px] font-semibold transition-opacity ${
              backendOk
                ? "bg-surface-container-low border border-outline-variant text-on-surface hover:bg-surface-container"
                : "bg-surface-container-low border border-outline-variant/30 text-outline/50 cursor-not-allowed"
            }`}
            title={!backendOk ? "Start the backend to sync" : "Sync all sources"}
          >
            {syncing === "*" ? (
              <span className="inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M21 12a9 9 0 11-9-9" />
                <path d="M21 3v6h-6" />
              </svg>
            )}
            Sync{!backendOk ? " (offline)" : ""}
          </button>
        </div>

        {/* Add Source Form */}
        {showForm && (
          <div className="p-5 mb-5 rounded-[12px] bg-surface-container-low border border-outline-variant space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-[14px] font-semibold text-on-surface">New Link</h3>
              <button
                onClick={() => { setShowForm(false); setFormError(null); }}
                className="text-[12px] text-outline hover:text-on-surface transition-colors"
              >
                Cancel
              </button>
            </div>

            <div>
              <label className="block text-[10px] font-bold text-outline mb-1.5 uppercase tracking-wider">Type</label>
              <div className="flex gap-2">
                {SOURCE_TYPES.map((opt) => (
                  <button
                    key={opt.id}
                    onClick={() => setForm({ ...form, source_type: opt.id })}
                    className={`flex-1 py-2 rounded-[6px] text-[12px] font-semibold transition-colors ${
                      form.source_type === opt.id
                        ? "bg-primary-container text-on-surface border border-primary-container"
                        : "bg-surface-container border border-outline-variant text-outline hover:border-outline"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <label className="block text-[10px] font-bold text-outline mb-1 uppercase tracking-wider">Label</label>
                <input
                  type="text"
                  value={form.label}
                  onChange={(e) => setForm({ ...form, label: e.target.value })}
                  placeholder="My Feed"
                  className="w-full px-3 py-2 rounded-[6px] bg-surface-container border border-outline-variant text-[13px] text-on-surface placeholder:text-outline/40 focus:outline-none focus:border-primary-container"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-[10px] font-bold text-outline mb-1 uppercase tracking-wider">URL *</label>
                <input
                  type="url"
                  value={form.uri}
                  onChange={(e) => setForm({ ...form, uri: e.target.value })}
                  placeholder={SOURCE_TYPES.find((t) => t.id === form.source_type)?.hint ?? "URL"}
                  className="w-full px-3 py-2 rounded-[6px] bg-surface-container border border-outline-variant text-[13px] text-on-surface font-mono placeholder:text-outline/40 focus:outline-none focus:border-primary-container"
                />
              </div>
              <div>
                <label className="block text-[10px] font-bold text-outline mb-1 uppercase tracking-wider">Interval (min)</label>
                <input
                  type="number"
                  value={form.interval_minutes}
                  onChange={(e) => setForm({ ...form, interval_minutes: Math.max(5, Number(e.target.value)) })}
                  min={5}
                  className="w-full px-3 py-2 rounded-[6px] bg-surface-container border border-outline-variant text-[13px] text-on-surface focus:outline-none focus:border-primary-container"
                />
              </div>
              <div>
                <label className="block text-[10px] font-bold text-outline mb-1 uppercase tracking-wider">Tags</label>
                <input
                  type="text"
                  value={form.tags}
                  onChange={(e) => setForm({ ...form, tags: e.target.value })}
                  placeholder="AI, news, tech"
                  className="w-full px-3 py-2 rounded-[6px] bg-surface-container border border-outline-variant text-[13px] text-on-surface placeholder:text-outline/40 focus:outline-none focus:border-primary-container"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-[10px] font-bold text-outline mb-1 uppercase tracking-wider">Schedule (cron)</label>
                <input
                  type="text"
                  value={form.schedule_cron}
                  onChange={(e) => setForm({ ...form, schedule_cron: e.target.value })}
                  placeholder="0 3 * * * (daily 3AM) — leave empty for interval-based"
                  className="w-full px-3 py-2 rounded-[6px] bg-surface-container border border-outline-variant text-[13px] text-on-surface font-mono placeholder:text-outline/40 focus:outline-none focus:border-primary-container"
                />
              </div>
            </div>

            {formError && <div className="text-[12px] text-error">{formError}</div>}

            <button
              onClick={handleAddSource}
              className="w-full py-2.5 rounded-[6px] text-[13px] font-semibold bg-primary-container text-on-surface hover:opacity-90 transition-opacity"
            >
              Add to List
            </button>
          </div>
        )}

        {/* Source List */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <span className="inline-block w-6 h-6 border-2 border-outline border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 && sources.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center gap-3">
            <svg className="w-10 h-10 text-outline/20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <path d="M4 6h16M4 12h16M4 18h16" />
            </svg>
            <p className="text-[14px] font-medium text-outline/80">No links yet</p>
            <p className="text-[12px] text-outline/50 max-w-[300px]">
              Add RSS feeds, GitHub repos, or web pages. They're saved locally and will sync when the backend is available.
            </p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex items-center justify-center py-16 text-center">
            <p className="text-[13px] text-outline/60">No {filter} sources</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            <div className="text-[11px] text-outline font-semibold mb-2">
              {filtered.length} link{filtered.length !== 1 ? "s" : ""}
              {!backendOk && " (offline)"}
            </div>
            {filtered.map((source) => (
              <div key={source.id}>
                {/* Main row */}
                <div
                  className="flex items-center justify-between p-3 rounded-[8px] bg-surface-container-low border border-outline-variant/50 group hover:border-outline-variant transition-colors cursor-pointer"
                  onClick={() => setExpandedId(expandedId === source.id ? null : source.id)}
                >
                  {/* Left: status + info */}
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

                  {/* Right: actions */}
                  <div className="flex items-center gap-0.5 ml-2 shrink-0">
                    <button
                      onClick={(e) => { e.stopPropagation(); void handleSyncOne(source.id); }}
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
                      onClick={(e) => { e.stopPropagation(); handleRemove(source.id); }}
                      className="p-2 rounded-[6px] text-on-surface-variant hover:text-error hover:bg-surface-container transition-colors"
                      title="Remove"
                    >
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                        <path d="M18 6L6 18M6 6l12 12" />
                      </svg>
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); setExpandedId(expandedId === source.id ? null : source.id); }}
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

                {/* Expanded details */}
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
        )}
      </div>
    </div>
  );
}
