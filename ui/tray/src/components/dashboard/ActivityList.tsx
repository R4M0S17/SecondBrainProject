import { useTranslation } from "react-i18next";
import type { RecentActivity } from "../../stores/dashboard";
import { formatRelativeTime } from "../../utils/time";

interface ActivityListProps {
  activities: RecentActivity[];
  onActivityClick?: (activity: RecentActivity) => void;
}

export default function ActivityList({ activities, onActivityClick }: ActivityListProps) {
  const { t } = useTranslation();

  return (
    <div className="bg-surface-container-low/40 border border-outline-variant/10 rounded-xl overflow-hidden">
      {activities.length === 0 ? (
        <div className="p-6 text-center">
          <span className="material-symbols-outlined text-[32px] text-on-surface-variant/20 mb-2">rocket_launch</span>
          <p className="text-[13px] text-on-surface-variant/50">{t("dashboard.no_activity")}</p>
          <p className="text-[11px] text-on-surface-variant/30 mt-1">{t("dashboard.no_activity_hint")}</p>
        </div>
      ) : activities.map((a) => (
        <button
          key={a.id}
          onClick={() => onActivityClick?.(a)}
          className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-container/40 transition-colors text-left border-b border-outline-variant/5 last:border-b-0"
        >
          <span className="material-symbols-outlined text-[18px] text-on-surface-variant/60">{a.icon}</span>
          <div className="flex-1 min-w-0">
            <p className="text-[13px] text-on-surface truncate">{a.label}</p>
            <p className="text-[11px] text-on-surface-variant/50 truncate">{a.description}</p>
          </div>
          <span className="text-[11px] text-on-surface-variant/40 shrink-0">{formatRelativeTime(a.timestamp)}</span>
        </button>
      ))}
    </div>
  );
}
