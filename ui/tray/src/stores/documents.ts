import { create } from "zustand";
import type { DocumentInfo } from "../api/types";
import { listDocuments, deleteDocument, startIndex } from "../api/client";

const CACHE_KEY = "cerebro_documents_cache";
const PENDING_KEY = "cerebro_documents_pending";

interface PendingOp {
  type: "add" | "delete";
  source_path: string;
  filename?: string;
}

function simplify(ops: PendingOp[]): PendingOp[] {
  const adds = new Map<string, PendingOp>();
  const dels = new Set<string>();
  for (const op of ops) {
    if (op.type === "add") {
      if (dels.has(op.source_path)) {
        dels.delete(op.source_path);
      } else {
        adds.set(op.source_path, op);
      }
    } else {
      if (adds.has(op.source_path)) {
        adds.delete(op.source_path);
      } else {
        dels.add(op.source_path);
      }
    }
  }
  return [
    ...adds.values(),
    ...Array.from(dels).map((sp) => ({ type: "delete" as const, source_path: sp })),
  ];
}

function loadCache(): DocumentInfo[] {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function saveCache(docs: DocumentInfo[]) {
  try { localStorage.setItem(CACHE_KEY, JSON.stringify(docs)); } catch {}
}

function loadPending(): PendingOp[] {
  try {
    const raw = localStorage.getItem(PENDING_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function savePending(ops: PendingOp[]) {
  try { localStorage.setItem(PENDING_KEY, JSON.stringify(ops)); } catch {}
}

interface DocumentsState {
  docs: DocumentInfo[];
  pendingCount: number;
  loading: boolean;
  error: string | null;
  usingCache: boolean;
  refresh: () => Promise<void>;
  addDocuments: (sourcePaths: string[]) => Promise<void>;
  removeDocument: (sourcePath: string) => Promise<void>;
  syncPending: () => Promise<void>;
  clearError: () => void;
}

export const useDocumentsStore = create<DocumentsState>((set, get) => ({
  docs: loadCache(),
  pendingCount: loadPending().length,
  loading: false,
  error: null,
  usingCache: false,

  refresh: async () => {
    set({ loading: true, error: null });
    try {
      const result = await listDocuments();
      saveCache(result);
      set({ docs: result, loading: false, usingCache: false });
      void get().syncPending();
    } catch {
      const cached = loadCache();
      set({ docs: cached, loading: false, usingCache: true });
    }
  },

  addDocuments: async (sourcePaths: string[]) => {
    try {
      await startIndex(sourcePaths);
      void get().refresh();
    } catch {
      const pending = loadPending();
      for (const sp of sourcePaths) {
        pending.push({
          type: "add",
          source_path: sp,
          filename: sp.split("/").pop() ?? sp,
        });
      }
      const ops = simplify(pending);
      savePending(ops);
      const newDocs: DocumentInfo[] = sourcePaths.map((sp) => ({
        source_path: sp,
        filename: sp.split("/").pop() ?? sp,
        file_modified: Date.now(),
      }));
      const docs = [...get().docs, ...newDocs];
      saveCache(docs);
      set({ docs, pendingCount: ops.length, usingCache: true });
    }
  },

  removeDocument: async (sourcePath: string) => {
    try {
      await deleteDocument(sourcePath);
      const docs = get().docs.filter((d) => d.source_path !== sourcePath);
      saveCache(docs);
      set({ docs, error: null });
    } catch {
      const ops = simplify([...loadPending(), { type: "delete", source_path: sourcePath }]);
      savePending(ops);
      const docs = get().docs.filter((d) => d.source_path !== sourcePath);
      saveCache(docs);
      set({ docs, pendingCount: ops.length, usingCache: true });
    }
  },

  syncPending: async () => {
    const ops = loadPending();
    if (ops.length === 0) return;

    const remaining: PendingOp[] = [];

    const adds = ops.filter((o) => o.type === "add").map((o) => o.source_path);
    if (adds.length > 0) {
      try {
        await startIndex(adds);
      } catch {
        remaining.push(...adds.map((sp) => ({ type: "add" as const, source_path: sp })));
      }
    }

    const deletes = ops.filter((o) => o.type === "delete").map((o) => o.source_path);
    for (const sp of deletes) {
      try {
        await deleteDocument(sp);
      } catch {
        remaining.push({ type: "delete" as const, source_path: sp });
      }
    }

    const simplified = simplify(remaining);
    savePending(simplified);
    set({ pendingCount: simplified.length });
    if (simplified.length === 0) {
      void get().refresh();
    }
  },

  clearError: () => set({ error: null }),
}));
