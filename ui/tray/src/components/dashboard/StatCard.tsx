interface StatCardProps {
  icon: string;
  label: string;
  value: string | number;
  hint?: string;
  color: string;
  onClick?: () => void;
}

export default function StatCard({ icon, label, value, hint, color, onClick }: StatCardProps) {
  const shared = "bg-surface-container-low/40 border border-outline-variant/10 rounded-xl p-4 flex items-center gap-3 transition-all duration-200";
  const interactive = onClick
    ? "cursor-pointer hover:bg-surface-container/60 hover:border-outline-variant/30 active:scale-[0.98]"
    : "";

  return (
    <div className={`${shared} ${interactive}`} onClick={onClick} role={onClick ? "button" : undefined} tabIndex={onClick ? 0 : undefined} onKeyDown={onClick ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } } : undefined}>
      <span className={`material-symbols-outlined text-[24px] ${color}`}>{icon}</span>
      <div>
        <p className="text-[22px] font-bold text-on-surface leading-none">{value}</p>
        <p className="text-[12px] text-on-surface-variant/60 mt-0.5">{label}</p>
        {hint && (
          <p className="text-[10px] text-on-surface-variant/40 mt-0.5 truncate">{hint}</p>
        )}
      </div>
    </div>
  );
}
