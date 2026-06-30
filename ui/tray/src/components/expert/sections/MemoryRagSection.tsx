import { useEffect, useState, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { getConfig, updateConfig } from "../../../api/client";
import type { AppConfig } from "../../../api/types";
import ToggleSwitch from "../../shared/ToggleSwitch";

interface FieldDef {
  key: keyof AppConfig;
  type: "int" | "float" | "bool" | "select";
  defaultVal: number | boolean | string;
  min?: number;
  max?: number;
  options?: string[];
}

const FIELDS: FieldDef[] = [
  { key: "short_term_max_messages", type: "int", defaultVal: 35, min: 1, max: 200 },
  { key: "context_budget_pct", type: "int", defaultVal: 85, min: 10, max: 100 },
  { key: "consolidation_target_pct", type: "int", defaultVal: 60, min: 10, max: 100 },
  { key: "session_resume_max_turns", type: "int", defaultVal: 8, min: 1, max: 50 },
  { key: "rag_top_k", type: "int", defaultVal: 5, min: 1, max: 50 },
  { key: "semantic_compression", type: "bool", defaultVal: true },
  { key: "embedding_cache_ttl_days", type: "int", defaultVal: 30, min: 1, max: 365 },
  { key: "embedding_cache_max_size", type: "int", defaultVal: 200, min: 10, max: 5000 },
  { key: "embeddings_backend", type: "select", defaultVal: "auto", options: ["auto", "local", "llamacpp"] },
];

const SHORT_TERM_KEYS = ["short_term_max_messages", "context_budget_pct", "consolidation_target_pct", "session_resume_max_turns"] as const;
const RAG_KEYS = ["rag_top_k", "semantic_compression", "embeddings_backend", "embedding_cache_ttl_days", "embedding_cache_max_size"] as const;

export default function MemoryRagSection() {
  const { t } = useTranslation();
  const [params, setParams] = useState<Record<string, number | boolean | string>>({});
  const [loaded, setLoaded] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    (async () => {
      try {
        const cfg = await getConfig();
        const p: Record<string, number | boolean | string> = {};
        for (const f of FIELDS) {
          const val = cfg[f.key];
          p[f.key] = (val !== undefined && val !== null) ? (val as number | boolean | string) : f.defaultVal;
        }
        setParams(p);
        setLoaded(true);
      } catch {
        const p: Record<string, number | boolean | string> = {};
        for (const f of FIELDS) p[f.key] = f.defaultVal;
        setParams(p);
        setLoaded(true);
      }
    })();
  }, []);

  const scheduleSave = useCallback((key: string, value: number | boolean | string) => {
    setParams((prev) => ({ ...prev, [key]: value }));
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        await updateConfig({ [key]: value } as Partial<AppConfig>);
      } catch {
        // silently fail
      }
    }, 500);
  }, []);

  useEffect(() => {
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, []);

  if (!loaded) return null;

  const renderField = (field: FieldDef) => {
    const val = params[field.key];
    if (field.type === "bool") {
      return (
        <div className="flex items-center justify-between px-3 py-2 rounded bg-surface-container-low">
          <label className="text-[12px] text-on-surface-variant font-medium">
            {t(`expert.memory.${field.key}`)}
          </label>
          <ToggleSwitch
            enabled={!!val}
            onChange={(v) => scheduleSave(field.key, v)}
            size="sm"
            ariaLabel={t(`expert.memory.${field.key}`)}
          />
        </div>
      );
    }
    if (field.type === "select" && field.options) {
      return (
        <div>
          <label className="text-[12px] text-on-surface-variant font-medium mb-1 block">
            {t(`expert.memory.${field.key}`)}
          </label>
          <select
            value={val as string}
            onChange={(e) => scheduleSave(field.key, e.target.value)}
            className="w-full py-2 px-3 rounded-[6px] text-[13px] bg-surface-container border border-outline-variant text-on-surface focus:outline-none focus:border-primary"
          >
            {field.options.map((opt) => (
              <option key={opt} value={opt}>
                {opt === "auto" ? t("expert.memory.embeddings_auto") : opt}
              </option>
            ))}
          </select>
        </div>
      );
    }
    if (field.type === "float") {
      return (
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-[12px] text-on-surface-variant font-medium">
              {t(`expert.memory.${field.key}`)}
            </label>
            <span className="text-[12px] font-mono text-on-surface">{val}%</span>
          </div>
          <input
            type="range"
            min={field.min ?? 0}
            max={field.max ?? 100}
            value={val as number}
            onChange={(e) => scheduleSave(field.key, parseInt(e.target.value))}
            className="w-full accent-primary-container h-1.5 rounded-full appearance-none cursor-pointer bg-surface-container-highest"
          />
        </div>
      );
    }
    return (
      <div>
        <label className="text-[12px] text-on-surface-variant font-medium mb-1 block">
          {t(`expert.memory.${field.key}`)}
        </label>
        <input
          type="number"
          min={field.min}
          max={field.max}
          value={val as number}
          onChange={(e) => scheduleSave(field.key, parseInt(e.target.value) || (field.min ?? 0))}
          className="w-full py-1.5 px-3 rounded-[6px] text-[13px] bg-surface-container border border-outline-variant text-on-surface focus:outline-none focus:border-primary"
        />
      </div>
    );
  };

  return (
    <div className="max-w-2xl space-y-8">
      {/* Short-term Memory */}
      <section>
        <h3 className="text-[13px] font-semibold text-on-surface mb-4">
          {t("expert.memory.short_term")}
        </h3>
        <div className="space-y-4">
          {FIELDS.filter((f) => (SHORT_TERM_KEYS as readonly string[]).includes(f.key)).map((f) => (
            <div key={f.key}>{renderField(f)}</div>
          ))}
        </div>
      </section>

      {/* RAG & Embeddings */}
      <section>
        <h3 className="text-[13px] font-semibold text-on-surface mb-4">
          {t("expert.memory.rag_embeddings")}
        </h3>
        <div className="space-y-4">
          {FIELDS.filter((f) => (RAG_KEYS as readonly string[]).includes(f.key)).map((f) => (
            <div key={f.key}>{renderField(f)}</div>
          ))}
        </div>
      </section>
    </div>
  );
}
