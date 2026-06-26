import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useDashboardStore } from "../../stores/dashboard";
import { useMemoryStore } from "../../stores/memory";
import { useTabStore, type LeftTab } from "../../stores/tab";
import { useWorkflowStore } from "../../stores/workflows";
import StatCard from "./StatCard";
import ActionCard from "./ActionCard";
import QuickChatCard from "./QuickChatCard";
import ActivityList from "./ActivityList";
import DashboardSkeleton from "./DashboardSkeleton";
import DashboardError from "./DashboardError";
import QuickNoteDialog from "../chat/QuickNoteDialog";
import AnalyzeFolderDialog from "./AnalyzeFolderDialog";

interface DashboardHomeProps {
  onDocumentsOpen?: () => void;
  onMemoryBrowserOpen?: () => void;
}

export default function DashboardHome({ onDocumentsOpen, onMemoryBrowserOpen }: DashboardHomeProps) {
  const { t } = useTranslation();
  const { status, recentActivity, loading, error, refresh } = useDashboardStore();
  const episodeCount = useMemoryStore((s) => s.stats.episodes_stored);
  const refreshMemory = useMemoryStore((s) => s.refresh);
  const setTab = useTabStore((s) => s.setTab);
  const setWorkflowCreateMode = useWorkflowStore((s) => s.setOpenCreateMode);
  const [analyzeFolderOpen, setAnalyzeFolderOpen] = useState(false);
  const quickNoteOpen = useDashboardStore((s) => s.quickNoteOpen);
  const setQuickNoteOpen = useDashboardStore((s) => s.setQuickNoteOpen);

  useEffect(() => {
    void refresh();
    void refreshMemory();
  }, [refresh, refreshMemory]);

  if (loading && !status) return <DashboardSkeleton />;
  if (error) return <DashboardError message={error} onRetry={refresh} />;

  const noFiles = !status?.indexed_files || status.indexed_files === 0;

  const stats = [
    { icon: "description", label: t("dashboard.files"), value: status?.indexed_files ?? 0, color: "text-primary-container", onClick: onDocumentsOpen },
    {
      icon: "psychology",
      label: t("dashboard.memories"),
      value: episodeCount,
      hint: status?.memory_hits
        ? t("dashboard.memories_hint", { hits: status.memory_hits })
        : undefined,
      color: "text-violet-400",
      onClick: onMemoryBrowserOpen,
    },
    { icon: "calendar_month", label: t("dashboard.events"), value: 0, color: "text-amber-400" },
    { icon: "public", label: t("dashboard.web"), value: t("dashboard.connected"), color: "text-success-green" },
  ];

  type DashboardAction = {
    icon: string;
    label: string;
    desc: string;
    disabled?: boolean;
    disabledReason?: string;
    kind: "tab" | "dialog";
    tab?: LeftTab;
    dialog?: "quickNote" | "analyzeFolder";
    beforeNavigate?: () => void;
  };

  const actions: DashboardAction[] = [
    { icon: "search", label: t("dashboard.search_files"), desc: t("dashboard.search_files_desc"), kind: "tab", tab: "sources", disabled: noFiles, disabledReason: t("dashboard.search_files_disabled_reason") },
    { icon: "folder_open", label: t("dashboard.analyze_folder"), desc: t("dashboard.analyze_folder_desc"), kind: "dialog", dialog: "analyzeFolder" },
    { icon: "account_tree", label: t("dashboard.create_workflow"), desc: t("dashboard.create_workflow_desc"), kind: "tab", tab: "workflows", beforeNavigate: () => setWorkflowCreateMode("record") },
    { icon: "edit_note", label: t("dashboard.quick_note"), desc: t("dashboard.quick_note_desc"), kind: "dialog", dialog: "quickNote" },
  ];

  return (
    <div className="flex-1 flex flex-col overflow-y-auto px-6 md:px-10 lg:px-12 pt-6 pb-8 dashboard-enter">
      <div className="mb-8 stagger-1">
        <h1 className="text-display-lg text-on-surface select-none">
          {t("dashboard.title")}
        </h1>
        <p className="text-body-base text-on-surface-variant/70 mt-1 select-none">
          {t("dashboard.subtitle")}
        </p>
      </div>

      <div className="mb-6 stagger-2">
        <QuickChatCard onClick={() => setTab("chat")} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8 stagger-3">
        {stats.map((s) => (
          <StatCard key={s.icon} icon={s.icon} label={s.label} value={s.value} hint={s.hint} color={s.color} onClick={s.onClick} />
        ))}
      </div>

      <div className="mb-8 stagger-4">
        <p className="text-label-caps text-outline tracking-wider mb-3 uppercase select-none">
          What do you need?
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {actions.map((a) => (
            <ActionCard
              key={a.icon}
              icon={a.icon}
              label={a.label}
              description={a.desc}
              onClick={() => {
                if (a.kind === "dialog") {
                  if (a.dialog === "quickNote") setQuickNoteOpen(true);
                  else if (a.dialog === "analyzeFolder") setAnalyzeFolderOpen(true);
                  return;
                }
                a.beforeNavigate?.();
                setTab(a.tab!);
              }}
              disabled={a.disabled}
              disabledReason={a.disabledReason}
            />
          ))}
        </div>
      </div>

      <div className="stagger-5">
        <p className="text-label-caps text-outline tracking-wider mb-3 uppercase select-none">
          {t("dashboard.recent_activity")}
        </p>
        <ActivityList activities={recentActivity} onActivityClick={(a) => a.tab && setTab(a.tab)} />
      </div>

      <QuickNoteDialog open={quickNoteOpen} onClose={() => setQuickNoteOpen(false)} />
      <AnalyzeFolderDialog isOpen={analyzeFolderOpen} onClose={() => setAnalyzeFolderOpen(false)} />
    </div>
  );
}
