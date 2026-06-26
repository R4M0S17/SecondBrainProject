import { useEffect, useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import { updateClaudeApiKey, getConfig, getHealth } from "../../api/client";

const LS_KEY = "cerebro_claude_api_key";

export default function ClaudeApiKeySection() {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [key, setKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [hasKey, setHasKey] = useState(false);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const syncedRef = useRef(false);

  const checkBackend = async () => {
    try {
      await getHealth();
      setBackendOk(true);
      return true;
    } catch {
      setBackendOk(false);
      return false;
    }
  };

  useEffect(() => {
    Promise.all([
      checkBackend(),
      getConfig().then((cfg) => setHasKey(!!cfg.claude_has_key)).catch(() => {}),
    ]).finally(() => setInitialLoading(false));
  }, []);

  useEffect(() => {
    if (editing && inputRef.current) inputRef.current.focus();
  }, [editing]);

  // Auto-sync localStorage key when backend becomes available
  useEffect(() => {
    if (!backendOk || syncedRef.current) return;
    const stored = localStorage.getItem(LS_KEY);
    if (stored) {
      syncedRef.current = true;
      updateClaudeApiKey(stored)
        .then(() => {
          localStorage.removeItem(LS_KEY);
          setHasKey(true);
          setMsg({ ok: true, text: t("claude.key_synced") });
        })
        .catch(() => {});
    }
  }, [backendOk]);

  const handleSave = async () => {
    if (!key.trim()) return;
    setSaving(true);
    setMsg(null);

    const alive = await checkBackend();
    if (!alive) {
      localStorage.setItem(LS_KEY, key.trim());
      setHasKey(true);
      setEditing(false);
      setKey("");
      setShowKey(false);
      setSaving(false);
            setMsg({ ok: true, text: t("claude.saved_locally") });
      return;
    }

    try {
      await updateClaudeApiKey(key.trim());
      setHasKey(true);
      setEditing(false);
      setKey("");
      setShowKey(false);
      setMsg({ ok: true, text: t("claude.key_saved") });
    } catch {
            setMsg({ ok: false, text: t("claude.save_failed") });
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setEditing(false);
    setKey("");
    setShowKey(false);
    setMsg(null);
  };

  return (
    <section>
      <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
        {t("claude.api_key")}
      </label>

      {initialLoading ? (
        <div className="flex items-center gap-2 px-3 py-2 rounded-[6px] bg-surface-container border border-outline-variant text-[12px] text-outline">
          <span className="inline-block w-3 h-3 border-2 border-outline border-t-transparent rounded-full animate-spin" />
          Checking backend…
        </div>
      ) : !editing ? (
        <div className="flex items-center justify-between px-3 py-2 rounded-[6px] bg-surface-container border border-outline-variant">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-outline" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <span className="text-[12px] text-on-surface">
              {hasKey ? "API key configured" : "No API key set"}
            </span>
          </div>
          <button
            onClick={() => setEditing(true)}
            className="text-[11px] font-semibold text-primary-container hover:underline"
          >
            {hasKey ? "Replace" : "Set up"}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                ref={inputRef}
                type={showKey ? "text" : "password"}
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="sk-ant-..."
                className="w-full px-3 py-2 pr-9 rounded-[6px] bg-surface-container border border-outline-variant text-on-surface text-[12px] placeholder:text-outline focus:outline-none focus:border-primary-container"
              />
              <button
                onClick={() => setShowKey(!showKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-outline hover:text-on-surface"
                tabIndex={-1}
                aria-label={showKey ? "Hide key" : "Show key"}
              >
                {showKey ? (
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
              onClick={handleSave}
              disabled={saving || !key.trim()}
              className="px-3 py-2 rounded-[6px] bg-primary-container text-on-surface text-[12px] font-semibold disabled:opacity-40 hover:bg-primary-container-hover transition-colors"
            >
              {saving ? "..." : "Save"}
            </button>
            <button
              onClick={handleCancel}
              className="px-3 py-2 rounded-[6px] border border-outline-variant text-outline text-[12px] font-semibold hover:text-on-surface transition-colors"
            >
              Cancel
            </button>
          </div>
          {backendOk === false && (
            <p className="text-[11px] text-outline">
              Backend offline — key will be saved locally and sent when backend starts
            </p>
          )}
          {msg && (
            <p className={`text-[11px] ${msg.ok ? "text-success-green" : "text-error"}`}>
              {msg.text}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
