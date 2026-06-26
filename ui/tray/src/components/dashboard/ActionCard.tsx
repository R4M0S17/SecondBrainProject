interface ActionCardProps {
  icon: string;
  label: string;
  description: string;
  onClick: () => void;
  disabled?: boolean;
  disabledReason?: string;
}

export default function ActionCard({ icon, label, description, onClick, disabled, disabledReason }: ActionCardProps) {
  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      title={disabled ? disabledReason : undefined}
      className={`flex items-center gap-4 p-4 rounded-xl bg-surface-container-low/40 border border-outline-variant/10
                 transition-all duration-200 group cursor-pointer text-left
                 ${disabled
                   ? "opacity-40 cursor-not-allowed"
                   : "hover:bg-surface-container/60 hover:border-outline-variant/30 active:scale-[0.98]"
                 }`}
    >
      <span className={`material-symbols-outlined text-[28px] transition-colors ${disabled ? "text-on-surface-variant/40" : "text-primary-container/80 group-hover:text-primary-container"}`}>
        {icon}
      </span>
      <div>
        <p className="text-[15px] font-semibold text-on-surface">{label}</p>
        <p className="text-[12px] text-on-surface-variant/60 mt-0.5">{description}</p>
      </div>
    </button>
  );
}
