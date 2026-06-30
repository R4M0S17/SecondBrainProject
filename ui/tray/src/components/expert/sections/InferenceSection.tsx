import { useEffect, useState, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { getConfig, updateConfig } from "../../../api/client";
import type { AppConfig } from "../../../api/types";

interface SliderField {
  key: keyof AppConfig;
  min: number;
  max: number;
  step: number;
  defaultVal: number;
}

const SLIDERS: SliderField[] = [
  { key: "temperature", min: 0.0, max: 2.0, step: 0.05, defaultVal: 0.7 },
  { key: "top_p", min: 0.0, max: 1.0, step: 0.05, defaultVal: 0.9 },
  { key: "repeat_penalty", min: 1.0, max: 1.5, step: 0.01, defaultVal: 1.1 },
];

const CONTEXT_OPTIONS = [1024, 2048, 4096, 8192];

export default function InferenceSection() {
  const { t } = useTranslation();
  const [params, setParams] = useState<Record<string, number | string | boolean>>({});
  const [loaded, setLoaded] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    (async () => {
      try {
        const cfg = await getConfig();
        const p: Record<string, number | string | boolean> = {};
        for (const s of SLIDERS) {
          p[s.key] = (cfg[s.key] as number) ?? s.defaultVal;
        }
        p.top_k = (cfg.top_k as number) ?? 40;
        p.context_length = (cfg.context_length as number) ?? 4096;
        p.profile = (cfg.profile as string) ?? "normal";
        p.llamacpp_url = (cfg.llamacpp_url as string) ?? "http://127.0.0.1:8080";
        p.embed_url = (cfg.embed_url as string) ?? "http://127.0.0.1:8082";
        setParams(p);
        setLoaded(true);
      } catch {
        const p: Record<string, number | string | boolean> = {};
        for (const s of SLIDERS) p[s.key] = s.defaultVal;
        p.top_k = 40;
        p.context_length = 4096;
        p.profile = "normal";
        p.llamacpp_url = "http://127.0.0.1:8080";
        p.embed_url = "http://127.0.0.1:8082";
        setParams(p);
        setLoaded(true);
      }
    })();
  }, []);

  const scheduleSave = useCallback((key: string, value: number | string | boolean) => {
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

  return (
    <div className="max-w-2xl space-y-8">
      {/* Generation Parameters */}
      <section>
        <h3 className="text-[13px] font-semibold text-on-surface mb-4">
          {t("expert.inference.generation_params")}
        </h3>
        <div className="space-y-4">
          {SLIDERS.map(({ key, min, max, step }) => (
            <div key={key}>
              <div className="flex items-center justify-between mb-1">
                <label className="text-[12px] text-on-surface-variant font-medium">
                  {t(`expert.inference.${key}`)}
                </label>
                <span className="text-[12px] font-mono text-on-surface tabular-nums w-10 text-right">
                  {Number(params[key] ?? 0).toFixed(step < 0.1 ? 2 : step < 1 ? 1 : 0)}
                </span>
              </div>
              <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={params[key] as number}
                onChange={(e) => scheduleSave(key, parseFloat(e.target.value))}
                className="w-full accent-primary-container h-1.5 rounded-full appearance-none cursor-pointer bg-surface-container-highest"
              />
            </div>
          ))}

          {/* Top-K */}
          <div>
            <label className="text-[12px] text-on-surface-variant font-medium mb-1 block">
              {t("expert.inference.top_k")}
            </label>
            <input
              type="number"
              min={1}
              max={200}
              value={params.top_k as number}
              onChange={(e) => scheduleSave("top_k", parseInt(e.target.value) || 1)}
              className="w-full py-1.5 px-3 rounded-[6px] text-[13px] bg-surface-container border border-outline-variant text-on-surface focus:outline-none focus:border-primary"
            />
          </div>

          {/* Context Length */}
          <div>
            <label className="text-[12px] text-on-surface-variant font-medium mb-1 block">
              {t("expert.inference.context_length")}
            </label>
            <select
              value={params.context_length as number}
              onChange={(e) => scheduleSave("context_length", parseInt(e.target.value))}
              className="w-full py-2 px-3 rounded-[6px] text-[13px] bg-surface-container border border-outline-variant text-on-surface focus:outline-none focus:border-primary"
            >
              {CONTEXT_OPTIONS.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </div>

          {/* Profile */}
          <div>
            <label className="text-[12px] text-on-surface-variant font-medium mb-1 block">
              {t("expert.inference.profile")}
            </label>
            <select
              value={params.profile as string}
              onChange={(e) => scheduleSave("profile", e.target.value)}
              className="w-full py-2 px-3 rounded-[6px] text-[13px] bg-surface-container border border-outline-variant text-on-surface focus:outline-none focus:border-primary"
            >
              <option value="normal">{t("expert.inference.profile_normal")}</option>
              <option value="deep">{t("expert.inference.profile_deep")}</option>
            </select>
          </div>
        </div>
      </section>

      {/* Server URLs */}
      <section>
        <h3 className="text-[13px] font-semibold text-on-surface mb-1">
          {t("expert.inference.server_urls")}
        </h3>
        <div className="bg-[#2a1e1e] border border-[#4a2e2e] rounded-lg px-4 py-2.5 mb-4">
          <p className="text-[11px] text-yellow-500 flex items-center gap-1.5">
            <span className="material-symbols-outlined text-[14px]">warning</span>
            {t("expert.inference.restart_warning")}
          </p>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-[12px] text-on-surface-variant font-medium mb-1 block">
              llamacpp URL
            </label>
            <input
              type="text"
              value={params.llamacpp_url as string}
              onChange={(e) => scheduleSave("llamacpp_url", e.target.value)}
              className="w-full py-1.5 px-3 rounded-[6px] text-[13px] bg-surface-container border border-outline-variant text-on-surface focus:outline-none focus:border-primary font-mono"
            />
          </div>
          <div>
            <label className="text-[12px] text-on-surface-variant font-medium mb-1 block">
              Embed URL
            </label>
            <input
              type="text"
              value={params.embed_url as string}
              onChange={(e) => scheduleSave("embed_url", e.target.value)}
              className="w-full py-1.5 px-3 rounded-[6px] text-[13px] bg-surface-container border border-outline-variant text-on-surface focus:outline-none focus:border-primary font-mono"
            />
          </div>
        </div>
      </section>
    </div>
  );
}
