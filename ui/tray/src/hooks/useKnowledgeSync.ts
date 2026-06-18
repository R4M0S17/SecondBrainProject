import { useCallback, useEffect, useRef, useState } from "react";
import {
  listSyncSources,
  addSyncSource as apiAddSource,
  exportSyncSources,
  importSyncSources as apiImportSources,
  removeSyncSource as apiRemoveSource,
  triggerSyncStream,
} from "../api/client";
import type { SyncSourceType } from "../api/types";
import type { EnrichedSource } from "../components/settings/SourceList";

const STORAGE_KEY = "cerebro_ks_sources";

const DEFAULT_FORM = {
  source_type: "rss" as SyncSourceType,
  uri: "",
  label: "",
  interval_minutes: 60,
  tags: "",
  schedule_cron: "",
};

function loadLocal(): EnrichedSource[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function saveLocal(sources: EnrichedSource[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(sources)); } catch {}
}

export function useKnowledgeSync() {
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
  const retryTimer = useRef<ReturnType<typeof setTimeout>>();

  const showMessage = (text: string, ok: boolean) => {
    setStatusMessage({ text, ok });
    setTimeout(() => setStatusMessage(null), 4000);
  };

  const tryBackend = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listSyncSources();
      setBackendOk(true);
      const local = loadLocal();
      const backendIds = new Set(data.map((s) => s.id));
      const localOnly = local.filter((s) => !backendIds.has(s.id));
      for (const s of localOnly) {
        try { await apiAddSource(s); } catch {}
      }
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
      retryTimer.current = setTimeout(() => void tryBackend(), 5000);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void tryBackend();
    return () => {
      if (retryTimer.current) clearTimeout(retryTimer.current);
    };
  }, [tryBackend]);

  useEffect(() => {
    const handler = () => {
      if (backendOk !== false) { void tryBackend(); }
    };
    window.addEventListener("knowledge-sync-complete", handler);
    return () => window.removeEventListener("knowledge-sync-complete", handler);
  }, [tryBackend, backendOk]);

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
      await triggerSyncStream(
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

  return {
    sources,
    loading,
    backendOk,
    syncing,
    showForm,
    form,
    formError,
    expandedId,
    filter,
    statusMessage,
    filtered,
    setShowForm,
    setForm,
    setFormError,
    setExpandedId,
    setFilter,
    handleAddSource,
    handleRemove,
    handleSyncAll,
    handleSyncOne,
    handleExport,
    handleImport,
    formatTime,
    showMessage,
  };
}
