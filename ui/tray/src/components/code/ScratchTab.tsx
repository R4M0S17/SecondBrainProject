import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useTabStore } from "../../stores/tab";
import { useChatStore } from "../../stores/chat";
import type { ScratchLang } from "../../stores/tab";

const LANGS: { id: ScratchLang; labelKey: string }[] = [
  { id: "python", labelKey: "code.lang_python" },
  { id: "shell", labelKey: "code.lang_shell" },
  { id: "javascript", labelKey: "code.lang_js" },
  { id: "plain", labelKey: "code.lang_plain" },
];

const PLACEHOLDERS: Record<ScratchLang, string> = {
  python: '# Python\ndef process(data):\n    return data\n\nresult = process([])',
  shell: '#!/bin/zsh\n# Shell Script\nfor f in *.txt; do\n  echo "$f"\ndone',
  javascript: '// JavaScript\nconst run = async () => {\n  const data = await fetch("/api/status")\n  return data.json()\n}',
  plain: '// Paste or write code here\n// Useful for preparing scripts before asking the agent to run them',
};

export default function ScratchTab() {
  const { t } = useTranslation();
  const scratch = useTabStore((s) => s.scratch);
  const setScratch = useTabStore((s) => s.setScratch);
  const scratchLang = useTabStore((s) => s.scratchLang);
  const setScratchLang = useTabStore((s) => s.setScratchLang);
  const setPendingChatAction = useChatStore((s) => s.setPendingChatAction);
  const setTab = useTabStore((s) => s.setTab);

  const handleSendToAgent = useCallback(() => {
    if (!scratch.trim()) return;
    const langHint: Record<ScratchLang, string> = {
      python: "python",
      shell: "shell",
      javascript: "javascript",
      plain: "",
    };
    const fence = langHint[scratchLang];
    const message = `Por favor ejecuta o analiza este código:\n\`\`\`${fence}\n${scratch}\n\`\`\``;
    setPendingChatAction({ query: message, autoSend: true });
    setTab("chat");
  }, [scratch, scratchLang, setPendingChatAction, setTab]);

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <p className="text-[11px] text-on-surface-variant/60 mb-4 flex items-center gap-1.5">
        <span className="material-symbols-outlined text-[14px] text-primary-container/60">info</span>
        {t("code.scratchpad")}
      </p>
      <div className="flex items-center justify-end gap-2 mb-3">
        <button
          onClick={handleSendToAgent}
          disabled={!scratch.trim()}
          className="flex items-center gap-1.5 px-3.5 py-2 bg-primary-container text-white text-[11px] font-medium rounded-lg hover:bg-primary-container/90 active:scale-[0.97] transition-all shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <span className="material-symbols-outlined text-[15px]">send</span>
          {t("code.send_to_agent")}
        </button>
        <button
          onClick={() => {
            navigator.clipboard.writeText(scratch).catch(() => {});
          }}
          className="flex items-center gap-1.5 px-3.5 py-2 text-[11px] font-medium rounded-lg border border-outline-variant/20 text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low active:scale-[0.97] transition-all"
        >
          <span className="material-symbols-outlined text-[15px]">content_copy</span>
          {t("code.copy")}
        </button>
        <button
          onClick={() => { setScratch(""); }}
          className="flex items-center gap-1.5 px-3.5 py-2 text-[11px] font-medium rounded-lg text-outline/50 hover:text-on-surface-variant hover:bg-surface-container-low active:scale-[0.97] transition-all"
        >
          <span className="material-symbols-outlined text-[15px]">delete</span>
          {t("code.clear")}
        </button>
      </div>
      <div className="flex-1 rounded-xl border border-outline-variant/15 bg-surface-container-low overflow-hidden flex flex-col min-h-0">
        <div className="flex items-center justify-between px-4 py-2 border-b border-outline-variant/10 bg-surface-container-lowest/30 shrink-0">
          <span className="text-[10px] text-outline/50 font-label-mono">
            {scratch.length > 0
              ? t("code.stats", { lines: scratch.split("\n").length, chars: scratch.length })
              : t("code.empty")}
          </span>
          <div className="flex gap-1">
            {LANGS.map((lang) => (
              <button
                key={lang.id}
                onClick={() => setScratchLang(lang.id)}
                className={`px-2 py-0.5 text-[10px] rounded font-mono transition-colors ${
                  scratchLang === lang.id
                    ? "bg-primary-container/15 text-primary-container"
                    : "text-outline/40 hover:text-outline/70"
                }`}
              >
                {t(lang.labelKey)}
              </button>
            ))}
          </div>
        </div>
        <textarea
          value={scratch}
          onChange={(e) => setScratch(e.target.value)}
          placeholder={PLACEHOLDERS[scratchLang]}
          className="flex-1 bg-transparent p-4 text-[13px] font-mono text-on-surface resize-none outline-none leading-relaxed placeholder-on-surface-variant/20"
          spellCheck={false}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              handleSendToAgent();
            }
          }}
        />
        {scratch.trim() && (
          <p className="text-[10px] text-outline/30 px-4 pb-2 text-right font-label-mono">
            {t("code.send_to_agent_hint")}
          </p>
        )}
      </div>
    </div>
  );
}
