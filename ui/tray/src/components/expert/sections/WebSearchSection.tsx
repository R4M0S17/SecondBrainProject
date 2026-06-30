import { useEffect, useState, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { getConfig, updateConfig } from "../../../api/client";
import type { AppConfig } from "../../../api/types";

interface WebField {
  key: keyof AppConfig;
  type: "int" | "select";
  defaultVal: number | string;
  min?: number;
  max?: number;
  options?: string[];
}

const FIELDS: WebField[] = [
  {
    key: "web_backend",
    type: "select",
    defaultVal: "duckduckgo",
    options: ["duckduckgo", "tavily"],
  },
  { key: "web_max_results", type: "int", defaultVal: 5, min: 1, max: 20 },
  { key: "web_max_chars", type: "int", defaultVal: 4000, min: 500, max: 20000 },
  { key: "web_timeout", type: "int", defaultVal: 15, min: 5, max: 60 },
];

export default function WebSearchSection() {
  const { t } = useTranslation();
  const [params, setParams] = useState<Record<string, number | string>>({});
  const [loaded, setLoaded] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    (async () => {
      try {
        const cfg = await getConfig();
        const p: Record<string, number | string> = {};
        for (const f of FIELDS) {
          const val = cfg[f.key];
          p[f.key] = (val !== undefined && val !== null)
            ? (val as number | string)
            : f.defaultVal;
        }
        setParams(p);
        setLoaded(true);
      } catch {
        const p: Record<string, number | string> = {};
        for (const f of FIELDS) p[f.key] = f.defaultVal;
        setParams(p);
        setLoaded(true);
      }
    })();
  }, []);

  const scheduleSave = useCallback((key: string, value: number | string) => {
    setParams((prev) => ({ ...prev, [key]: value }));
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        await updateConfig({ [key]: value } as Partial<AppConfig>);
      } catch {}
    }, 500);
  }, []);

  useEffect(() => {
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, []);

  if (!loaded) return null;

  return (
    <div className="max-w-2xl space-y-6">
      <h3 className="text-[13px] font-semibold text-on-surface mb-4">
        {t("expert.web_search.title")}
      </h3>
      <div className="space-y-4">
        {FIELDS.map((f) => (
          <div key={f.key}>
            <label className="text-[12px] text-on-surface-variant font-medium mb-1 block">
              {t(`expert.web_search.${f.key}`)}
            </label>
            {f.type === "select" && f.options ? (
              <select
                value={params[f.key] as string}
                onChange={(e) => scheduleSave(f.key, e.target.value)}
                className="w-full py-2 px-3 rounded-[6px] text-[13px] bg-surface-container border border-outline-variant text-on-surface focus:outline-none focus:border-primary"
              >
                {f.options.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            ) : (
              <input
                type="number"
                min={f.min}
                max={f.max}
                value={params[f.key] as number}
                onChange={(e) => scheduleSave(f.key, parseInt(e.target.value) || (f.min ?? 0))}
                className="w-full py-1.5 px-3 rounded-[6px] text-[13px] bg-surface-container border border-outline-variant text-on-surface focus:outline-none focus:border-primary"
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
