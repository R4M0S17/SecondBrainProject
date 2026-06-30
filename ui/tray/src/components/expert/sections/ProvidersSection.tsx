import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getConfig, updateConfig } from "../../../api/client";
import type { AppConfig } from "../../../api/types";

interface ApiKeyField {
  key: keyof AppConfig;
  label: string;
  envVar: string;
  placeholder: string;
}

const API_KEYS: ApiKeyField[] = [
  { key: "anthropic_api_key", label: "ANTHROPIC_API_KEY", envVar: "ANTHROPIC_API_KEY", placeholder: "sk-ant-..." },
  { key: "tavily_api_key", label: "TAVILY_API_KEY", envVar: "TAVILY_API_KEY", placeholder: "tvly-..." },
  { key: "cerebro_api_key", label: "CEREBRO_API_KEY", envVar: "CEREBRO_API_KEY", placeholder: "optional" },
];

export default function ProvidersSection() {
  const { t } = useTranslation();
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [keyValues, setKeyValues] = useState<Record<string, string>>({});
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getConfig()
      .then((cfg) => { setConfig(cfg); setLoaded(true); })
      .catch(() => setLoaded(true));
  }, []);

  const hasKey = (key: keyof AppConfig) => {
    if (!config) return false;
    const val = config[key];
    return !!val && val !== "";
  };

  const handleSaveKey = async (field: ApiKeyField) => {
    const val = keyValues[field.key]?.trim();
    if (!val) return;
    setSaving(true);
    try {
      const updated = await updateConfig({ [field.key]: val } as Partial<AppConfig>);
      setConfig(updated);
      setEditingKey(null);
      setKeyValues((prev) => ({ ...prev, [field.key]: "" }));
    } catch {
      // silently fail
    } finally {
      setSaving(false);
    }
  };

  if (!loaded) return null;

  return (
    <div className="max-w-2xl space-y-8">
      {/* API Keys */}
      <section>
        <h3 className="text-[13px] font-semibold text-on-surface mb-4">
          {t("expert.providers.api_keys")}
        </h3>
        <div className="space-y-2">
          {API_KEYS.map((field) => {
            const configured = hasKey(field.key);
            const isEditing = editingKey === field.key;
            return (
              <div
                key={field.key}
                className="flex items-center justify-between px-3 py-2 rounded-lg bg-surface-container-low border border-outline-variant/30"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${configured ? "bg-success-green" : "bg-outline"}`} />
                  <span className="text-[12px] font-medium text-on-surface truncate">
                    {field.label}
                  </span>
                  <span className="text-[10px] text-outline">
                    {configured
                      ? t("expert.providers.key_configured")
                      : t("expert.providers.key_not_configured")}
                  </span>
                </div>
                {!isEditing ? (
                  <button
                    onClick={() => {
                      setEditingKey(field.key);
                      setKeyValues((prev) => ({ ...prev, [field.key]: "" }));
                    }}
                    className="text-[11px] font-semibold text-primary-container hover:underline shrink-0"
                  >
                    {configured ? t("expert.providers.replace") : t("expert.providers.add")}
                  </button>
                ) : null}
              </div>
            );
          })}
        </div>

        {/* Inline editor for active key */}
        {editingKey && (() => {
          const field = API_KEYS.find((k) => k.key === editingKey)!;
          return (
            <div className="mt-3 space-y-2 pl-1">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    type={showKeys[editingKey] ? "text" : "password"}
                    value={keyValues[editingKey] ?? ""}
                    onChange={(e) => setKeyValues((prev) => ({ ...prev, [editingKey]: e.target.value }))}
                    placeholder={field.placeholder}
                    className="w-full px-3 py-2 pr-9 rounded-[6px] bg-surface-container border border-outline-variant text-on-surface text-[12px] placeholder:text-outline focus:outline-none focus:border-primary"
                    autoFocus
                  />
                  <button
                    onClick={() => setShowKeys((prev) => ({ ...prev, [editingKey]: !prev[editingKey] }))}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-outline hover:text-on-surface"
                    tabIndex={-1}
                    aria-label="Toggle visibility"
                  >
                    {showKeys[editingKey] ? (
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                        <line x1="1" y1="1" x2="23" y2="23" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
                <button
                  onClick={() => handleSaveKey(field)}
                  disabled={saving || !keyValues[editingKey]?.trim()}
                  className="px-3 py-2 rounded-[6px] bg-primary-container text-on-surface text-[12px] font-semibold disabled:opacity-40 hover:bg-primary-container-hover transition-colors"
                >
                  {saving ? "..." : t("expert.providers.save")}
                </button>
                <button
                  onClick={() => setEditingKey(null)}
                  className="px-3 py-2 rounded-[6px] border border-outline-variant text-outline text-[12px] font-semibold hover:text-on-surface transition-colors"
                >
                  {t("expert.providers.cancel")}
                </button>
              </div>
              <p className="text-[10px] text-outline">
                {t("expert.providers.key_hint")}
              </p>
            </div>
          );
        })()}
      </section>

      {/* Paths */}
      <section>
        <h3 className="text-[13px] font-semibold text-on-surface mb-4">
          {t("expert.providers.paths")}
        </h3>

        {/* Watched folders (editable) */}
        <div className="mb-4">
          <label className="text-[12px] text-on-surface-variant font-medium mb-2 block">
            {t("expert.providers.watched_folders")}
          </label>
          <PathList
            paths={config?.watched_folders ?? []}
            onRemove={async (path) => {
              const updated = config?.watched_folders.filter((p) => p !== path) ?? [];
              try {
                const cfg = await updateConfig({ watched_folders: updated } as Partial<AppConfig>);
                setConfig(cfg);
              } catch {}
            }}
            onAdd={async (path) => {
              const updated = [...(config?.watched_folders ?? []), path];
              try {
                const cfg = await updateConfig({ watched_folders: updated } as Partial<AppConfig>);
                setConfig(cfg);
              } catch {}
            }}
          />
        </div>
      </section>
    </div>
  );
}

function PathList({
  paths,
  onRemove,
  onAdd,
}: {
  paths: string[];
  onRemove: (path: string) => void;
  onAdd: (path: string) => void;
}) {
  const { t } = useTranslation();
  const [adding, setAdding] = useState(false);
  const [newPath, setNewPath] = useState("");

  const handleAdd = () => {
    const trimmed = newPath.trim();
    if (!trimmed || paths.includes(trimmed)) return;
    onAdd(trimmed);
    setNewPath("");
    setAdding(false);
  };

  return (
    <div>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {paths.map((p) => (
          <span
            key={p}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container-higher text-[11px] text-on-surface font-mono"
          >
            {p}
            <button
              onClick={() => onRemove(p)}
              className="text-outline hover:text-error transition-colors"
            >
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </span>
        ))}
      </div>
      {adding ? (
        <div className="flex gap-2">
          <input
            type="text"
            value={newPath}
            onChange={(e) => setNewPath(e.target.value)}
            placeholder="~/NewFolder"
            className="flex-1 py-1.5 px-3 rounded-[6px] text-[12px] bg-surface-container border border-outline-variant text-on-surface placeholder:text-outline focus:outline-none focus:border-primary"
            onKeyDown={(e) => { if (e.key === "Enter") handleAdd(); if (e.key === "Escape") setAdding(false); }}
            autoFocus
          />
          <button
            onClick={handleAdd}
            disabled={!newPath.trim()}
            className="px-2.5 py-1.5 rounded-[6px] bg-primary-container text-on-surface text-[11px] font-semibold disabled:opacity-40"
          >
            {t("expert.providers.add")}
          </button>
          <button
            onClick={() => { setAdding(false); setNewPath(""); }}
            className="px-2.5 py-1.5 rounded-[6px] border border-outline-variant text-outline text-[11px] font-semibold"
          >
            {t("expert.providers.cancel")}
          </button>
        </div>
      ) : (
        <button
          onClick={() => setAdding(true)}
          className="text-[11px] font-semibold text-primary-container hover:underline flex items-center gap-1"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M12 5v14M5 12h14" />
          </svg>
          {t("expert.providers.add_path")}
        </button>
      )}
    </div>
  );
}
