import { Suspense, lazy, useState, useCallback, useEffect } from "react";
import Header from "./Header";
import LeftSidebar from "./LeftSidebar";
import ChatWindow from "../components/chat/ChatWindow";
import AgentBar from "../components/chat/AgentBar";
import SystemSidebar from "../components/status/SystemSidebar";
import StatusBar from "../components/status/StatusBar";
import CodePanel from "../components/code/CodePanel";
import SourcesView from "../components/settings/SourcesView";
import DashboardHome from "../components/dashboard/DashboardHome";
import WorkflowHub from "../components/automation/WorkflowHub";
import RecordingOverlay from "../components/automation/RecordingOverlay";
import MemoryView from "../components/memory/MemoryView";
import { useTabStore } from "../stores/tab";
import { useSettingsStore } from "../stores/settings";
import { useDashboardStore } from "../stores/dashboard";
import { useDebugStore } from "../stores/debug";

const SettingsPanel = lazy(() => import("../components/settings/SettingsPanel"));
const DocumentsPanel = lazy(() => import("../components/documents/DocumentsPanel"));
const MemoryBrowserPanel = lazy(() => import("../components/memory/MemoryBrowserPanel"));
const TimeTravelView = lazy(() => import("../components/debug/TimeTravelView"));
const GlobalSearch = lazy(() => import("../components/search/GlobalSearch"));
const ExpertSettingsModal = lazy(() => import("../components/expert/ExpertSettingsModal"));

export default function MainLayout() {
  const { isOpen: settingsOpen, open: openSettings, expertOpen } = useSettingsStore();
  const [docsOpen, setDocsOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const debugPanelOpen = useDebugStore((s) => s.debugPanelOpen);
  const setDebugPanelOpen = useDebugStore((s) => s.setDebugPanelOpen);
  const [memoriesOpen, setMemoriesOpen] = useState(false);
  const closeDocs = useCallback(() => setDocsOpen(false), []);
  const closeSearch = useCallback(() => setSearchOpen(false), []);
  const closeDebug = useCallback(() => setDebugPanelOpen(false), []);
  const closeMemories = useCallback(() => setMemoriesOpen(false), []);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const activeTab = useTabStore((s) => s.activeTab);

  useEffect(() => {
    let cleanup: (() => void) | undefined;
    import("@tauri-apps/api/window")
      .then(({ getCurrentWindow }) => {
        const w = getCurrentWindow();
        w.isFullscreen().then(setIsFullscreen);
        w.onResized(() => {
          w.isFullscreen().then(setIsFullscreen);
        }).then((fn) => { cleanup = fn; });
      })
      .catch(() => {});
    return () => cleanup?.();
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen(true);
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "N") {
        e.preventDefault();
        useDashboardStore.getState().setQuickNoteOpen(true);
      }
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "F") {
        e.preventDefault();
        useDashboardStore.getState().setSearchDocsOpen(true);
      }
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === ",") {
        e.preventDefault();
        useSettingsStore.getState().openExpert();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const handleOpenSettings = useCallback(() => {
    setDocsOpen(false);
    openSettings();
  }, [openSettings]);

  return (
    <div className="flex flex-col w-full h-full bg-background overflow-hidden">
      {!isFullscreen && <div className="h-7 shrink-0" data-tauri-drag-region />}
      <Header
        onSettingsOpen={handleOpenSettings}
      />

      <div className="flex flex-1 overflow-hidden">
        <LeftSidebar />
        <div className="flex-1 flex flex-col relative w-full min-w-0 min-h-0">
          {activeTab === "home" ? (
            <DashboardHome onDocumentsOpen={() => setDocsOpen(true)} />
          ) : activeTab === "workflows" ? (
            <WorkflowHub />
          ) : activeTab === "memory" ? (
            <MemoryView />
          ) : activeTab === "code" ? (
            <CodePanel />
          ) : activeTab === "sources" ? (
            <SourcesView />
          ) : (
            <div className="flex-1 flex flex-col px-4 md:px-6 lg:px-8 pt-2 pb-6 w-full min-w-0 min-h-0">
              <AgentBar />
              <ChatWindow className="flex-1 min-h-0" />
            </div>
          )}
        </div>
        <SystemSidebar />
      </div>

      <StatusBar />

      {settingsOpen && (
        <Suspense fallback={null}>
          <SettingsPanel />
        </Suspense>
      )}
      {expertOpen && (
        <Suspense fallback={null}>
          <ExpertSettingsModal />
        </Suspense>
      )}
      {docsOpen && (
        <Suspense fallback={null}>
          <DocumentsPanel isOpen={docsOpen} onClose={closeDocs} />
        </Suspense>
      )}
      {debugPanelOpen && (
        <Suspense fallback={null}>
          <TimeTravelView onClose={closeDebug} />
        </Suspense>
      )}
      {memoriesOpen && (
        <Suspense fallback={null}>
          <MemoryBrowserPanel isOpen={memoriesOpen} onClose={closeMemories} />
        </Suspense>
      )}
      {searchOpen && (
        <Suspense fallback={null}>
          <GlobalSearch onClose={closeSearch} />
        </Suspense>
      )}
      {/* Always-visible recording overlay — works in dev and Tauri */}
      <RecordingOverlay />
    </div>
  );
}
