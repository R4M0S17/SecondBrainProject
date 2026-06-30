import { useTranslation } from "react-i18next";

interface QuickChatCardProps {
  onClick: () => void;
}

export default function QuickChatCard({ onClick }: QuickChatCardProps) {
  const { t } = useTranslation();
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-5 p-5 rounded-2xl
                 bg-gradient-to-r from-primary-container/20 via-primary-container/10 to-transparent
                 border border-primary-container/25 hover:border-primary-container/50
                 shadow-lg shadow-primary-container/5 hover:shadow-primary-container/10
                 transition-all duration-300 group cursor-pointer text-left
                 active:scale-[0.99]"
    >
      <span className="material-symbols-outlined text-[36px] text-primary-container
                       group-hover:scale-110 transition-transform duration-300">
        chat
      </span>
      <div className="flex-1">
        <p className="text-[17px] font-bold text-on-surface group-hover:text-primary-container transition-colors">
          {t("dashboard.quick_chat")}
        </p>
        <p className="text-[13px] text-on-surface-variant/60 mt-0.5">
          {t("dashboard.quick_chat_desc")}
        </p>
      </div>
      <span className="material-symbols-outlined text-[20px] text-on-surface-variant/30
                       group-hover:text-primary-container/60 group-hover:translate-x-1 transition-all">
        arrow_forward
      </span>
    </button>
  );
}
