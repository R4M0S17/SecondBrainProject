import type { ExpertSection } from "../../stores/settings";

interface ExpertNavItemProps {
  id: ExpertSection;
  icon: string;
  label: string;
  active: boolean;
  onClick: () => void;
}

export default function ExpertNavItem({ id, icon, label, active, onClick }: ExpertNavItemProps) {
  return (
    <button
      onClick={onClick}
      data-section={id}
      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium transition-all text-left ${
        active
          ? "bg-primary-container/15 text-primary-container shadow-sm border-l-[3px] border-primary-container"
          : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface border-l-[3px] border-transparent"
      }`}
    >
      <span className="material-symbols-outlined text-[16px]">{icon}</span>
      {label}
    </button>
  );
}
