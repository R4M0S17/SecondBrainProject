import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useWorkflowStore } from "../../stores/workflows";
import WorkflowHeader from "./WorkflowHeader";
import WorkflowTypeTabs from "./WorkflowTypeTabs";
import WorkflowList from "./WorkflowList";
import WorkflowDetail from "./WorkflowDetail";
import WorkflowEmpty from "./WorkflowEmpty";
import { openAccessibilitySettings } from "../../utils/macosSettings";
import RecordingBanner from "./RecordingBanner";
import RecipeTemplateGrid from "./RecipeTemplateGrid";

export default function WorkflowHub() {
  const { t } = useTranslation();
  const {
    workflows,
    selected,
    selectedId,
    isLoading,
    isRunning,
    runResult,
    lastRunSuccess,
    runs,
    templates,
    templatesLoaded,
    error,
    searchQuery,
    viewTab,
    recordingStatus,
    isRecording,
    isGeneralizing,
    openCreateMode,
    setSearchQuery,
    setViewTab,
    setOpenCreateMode,
    loadAll,
    loadTemplates,
    select,
    remove,
    execute,
    installTemplate,
    importFromFile,
    updateWorkflow,
    startRecording,
    pollRecordingStatus,
    stopRecording,
    cancelRecording,
  } = useWorkflowStore();

  const [installingTemplateId, setInstallingTemplateId] = useState<string | null>(null);

  useEffect(() => {
    void loadAll();
    void loadTemplates();
  }, [loadAll, loadTemplates]);

  useEffect(() => {
    if (openCreateMode === "record") {
      setOpenCreateMode(null);
      void startRecording().catch(() => {});
    } else if (openCreateMode === "templates") {
      setOpenCreateMode(null);
      setViewTab("templates");
    }
  }, [openCreateMode, setOpenCreateMode, setViewTab, startRecording]);

  const tabWorkflows = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    let list = workflows ?? [];
    if (viewTab === "routines") {
      list = list.filter((w) => w.workflow_type !== "recipe");
    } else if (viewTab === "recipes") {
      list = list.filter((w) => w.workflow_type === "recipe");
    }
    if (!q) return list;
    return list.filter(
      (w) =>
        w.name.toLowerCase().includes(q) ||
        w.description.toLowerCase().includes(q) ||
        w.tags.some((tag) => tag.toLowerCase().includes(q)),
    );
  }, [workflows, searchQuery, viewTab]);

  const handleRecordStart = useCallback(() => {
    void startRecording().catch(() => {});
  }, [startRecording]);

  const handleStop = useCallback(() => {
    void stopRecording();
  }, [stopRecording]);

  const handleCancel = useCallback(() => {
    void cancelRecording();
  }, [cancelRecording]);

  const handleRename = useCallback(
    (id: string, name: string) => {
      void updateWorkflow(id, { name });
    },
    [updateWorkflow],
  );

  const handleRun = useCallback(
    (id: string, params: Record<string, string>, options?: { dryRun?: boolean }) => {
      void execute(id, params, options);
    },
    [execute],
  );

  const handleUpdateSteps = useCallback(
    (id: string, steps: import("../../api/types").WorkflowStep[]) => {
      void updateWorkflow(id, { steps });
    },
    [updateWorkflow],
  );

  const handleQuickRun = useCallback(
    (id: string) => {
      void select(id).then(() => {
        const wf = useWorkflowStore.getState().selected;
        if (wf && wf.parameters.length === 0) {
          void execute(id, {});
        }
      });
    },
    [select, execute],
  );

  const handleInstallTemplate = useCallback(
    async (templateId: string) => {
      setInstallingTemplateId(templateId);
      try {
        await installTemplate(templateId);
      } finally {
        setInstallingTemplateId(null);
      }
    },
    [installTemplate],
  );

  const handleImportFile = useCallback(
    (file: File) => {
      void importFromFile(file);
    },
    [importFromFile],
  );

  const showEmpty =
    viewTab !== "templates" &&
    tabWorkflows.length === 0 &&
    !isLoading &&
    !isRecording &&
    !isGeneralizing;

  return (
    <div className="flex flex-col w-full h-full bg-background text-on-surface dashboard-enter">
      <WorkflowHeader
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onRecordStart={handleRecordStart}
        onImport={handleImportFile}
        isRecording={isRecording}
        isGeneralizing={isGeneralizing}
      />
      <WorkflowTypeTabs active={viewTab} onChange={setViewTab} />

      {error && (
        <div className="mx-6 md:mx-10 mt-3 px-4 py-2 text-[12px] text-red-300 bg-red-900/20 rounded-xl border border-red-800/30 flex flex-wrap items-center gap-3">
          <span>{error.startsWith("workflows.error.") ? t(error) : error}</span>
          {(error === "workflows.error.accessibility_required" ||
            error === "workflows.error.recorder_unavailable") && (
            <button
              type="button"
              onClick={() => void openAccessibilitySettings()}
              className="text-[11px] px-2 py-1 rounded-lg bg-surface-container-low text-on-surface-variant hover:bg-surface-container/60"
            >
              {t("workflows.open_accessibility_settings")}
            </button>
          )}
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        {viewTab === "templates" ? (
          <RecipeTemplateGrid
            templates={templates}
            templatesLoaded={templatesLoaded}
            onInstall={handleInstallTemplate}
            installingId={installingTemplateId}
          />
        ) : showEmpty ? (
          <WorkflowEmpty
            variant={viewTab}
            onRecordStart={handleRecordStart}
            onOpenTemplates={() => setViewTab("templates")}
            onInstallTemplate={handleInstallTemplate}
          />
        ) : (
          <>
            <WorkflowList
              workflows={tabWorkflows}
              selectedId={selectedId}
              isLoading={isLoading}
              viewTab={viewTab}
              onSelect={(id) => void select(id)}
              onQuickRun={handleQuickRun}
            />
            <main className="flex-1 overflow-y-auto min-w-0">
              {selected ? (
                <WorkflowDetail
                  workflow={selected}
                  runs={runs}
                  runResult={runResult}
                  lastRunSuccess={lastRunSuccess}
                  isRunning={isRunning}
                  onRun={handleRun}
                  onDelete={(id) => void remove(id)}
                  onRename={handleRename}
                  onUpdateSteps={handleUpdateSteps}
                />
              ) : (
                <div className="flex items-center justify-center h-full text-[13px] text-outline px-6">
                  {tabWorkflows.length > 0
                    ? t("workflows.select_prompt")
                    : t("workflows.empty_title")}
                </div>
              )}
            </main>
          </>
        )}
      </div>

      <RecordingBanner
        status={recordingStatus}
        isGeneralizing={isGeneralizing}
        onPoll={() => void pollRecordingStatus()}
        onStop={handleStop}
        onCancel={handleCancel}
      />
    </div>
  );
}
