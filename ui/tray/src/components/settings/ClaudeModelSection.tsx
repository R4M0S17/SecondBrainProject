import { useTranslation } from "react-i18next";

const CLAUDE_MODELS = [
  { id: "claude-fable-5", label: "Fable 5", ctx: "1M" },
  { id: "claude-opus-4-8", label: "Opus 4.8", ctx: "1M" },
  { id: "claude-sonnet-4-6", label: "Sonnet 4.6", ctx: "1M" },
  { id: "claude-haiku-4-5", label: "Haiku 4.5", ctx: "200K" },
];

export default function ClaudeModelSection() {
  const { t } = useTranslation();
  return (
    <section>
      <label className="block text-[11px] font-bold tracking-[0.05em] text-outline uppercase mb-2">
        {t("claude.models")}
      </label>
      <div className="space-y-1">
        {CLAUDE_MODELS.map((m) => (
          <div
            key={m.id}
            className="flex items-center justify-between px-3 py-2 rounded-[6px] bg-surface-container border border-outline-variant"
          >
            <div>
              <span className="text-[12px] font-medium text-on-surface">{m.label}</span>
              <span className="text-outline ml-2 text-[11px]">{m.id}</span>
            </div>
            <span className="text-[10px] text-outline font-mono">{m.ctx}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
