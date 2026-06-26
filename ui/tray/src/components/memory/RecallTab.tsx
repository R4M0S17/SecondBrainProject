import { useTranslation } from "react-i18next";
import { useMemoryStore } from "../../stores/memory";
import MemoryRecallSearch from "./MemoryRecallSearch";

interface RecallTabProps {
  compact?: boolean;
}

export default function RecallTab({ compact: _compact = false }: RecallTabProps) {
  const { t } = useTranslation();
  const { searchRecall, usingMock } = useMemoryStore();

  return (
    <section className="bg-surface-container-low/20 border border-outline-variant/10 rounded-xl p-4 md:p-5">
      <div className="mb-3">
        <h2 className="text-[14px] font-semibold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px] text-outline">psychology</span>
          {t("memory.recall_test")}
        </h2>
        <p className="text-[11px] text-on-surface-variant/60 mt-1">{t("memory.recall_test_hint")}</p>
      </div>
      <MemoryRecallSearch onSearch={searchRecall} usingMock={usingMock} />
    </section>
  );
}
