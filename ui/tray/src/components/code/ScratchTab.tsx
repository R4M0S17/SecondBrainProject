import { useTranslation } from "react-i18next";
import { useTabStore } from "../../stores/tab";

export default function ScratchTab() {
  const { t } = useTranslation();
  const scratch = useTabStore((s) => s.scratch);
  const setScratch = useTabStore((s) => s.setScratch);

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <p className="text-[11px] text-on-surface-variant/60 mb-4 flex items-center gap-1.5">
        <span className="material-symbols-outlined text-[14px] text-primary-container/60">info</span>
        {t("code.scratchpad")}
      </p>
      <div className="flex items-center justify-end gap-2 mb-3">
        <button
          onClick={() => {
            navigator.clipboard.writeText(scratch).catch(() => {});
          }}
          className="flex items-center gap-1.5 px-3.5 py-2 bg-primary-container text-white text-[11px] font-medium rounded-lg hover:bg-primary-container/90 active:scale-[0.97] transition-all shadow-sm"
        >
          <span className="material-symbols-outlined text-[15px]">content_copy</span>
          {t("code.copy")}
        </button>
        <button
          onClick={() => { setScratch(""); }}
          className="flex items-center gap-1.5 px-3.5 py-2 text-[11px] font-medium rounded-lg border border-outline-variant/20 text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low active:scale-[0.97] transition-all"
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
        </div>
        <textarea
          value={scratch}
          onChange={(e) => setScratch(e.target.value)}
          placeholder='// Paste or write code here&#10;// Useful for preparing scripts before asking the agent to run them&#10;// Example:&#10;def hello():&#10;    print("Hello, world!")&#10;&#10;hello()'
          className="flex-1 bg-transparent p-4 text-[13px] font-mono text-on-surface resize-none outline-none leading-relaxed placeholder-on-surface-variant/20"
          spellCheck={false}
        />
      </div>
    </div>
  );
}
