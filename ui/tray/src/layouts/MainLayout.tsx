import { Suspense, lazy, useState, useCallback, useEffect } from "react";
import Header from "./Header";
import LeftSidebar from "./LeftSidebar";
import ChatWindow from "../components/chat/ChatWindow";
import AgentBar from "../components/chat/AgentBar";
import SystemSidebar from "../components/status/SystemSidebar";
import StatusBar from "../components/status/StatusBar";
import ToolsPanel from "../components/tools/ToolsPanel";
import CodePanel from "../components/code/CodePanel";
import TimeTravelView from "../components/debug/TimeTravelView";
import SourcesView from "../components/settings/SourcesView";
import { useSettingsStore } from "../stores/settings";
import { useTabStore } from "../stores/tab";

const SettingsPanel = lazy(() => import("../components/settings/SettingsPanel"));
const DocumentsPanel = lazy(() => import("../components/documents/DocumentsPanel"));

export default function MainLayout() {
  const { isOpen: settingsOpen, open: openSettings, close: closeSettings } = useSettingsStore();
  const [docsOpen, setDocsOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const closeDocs = useCallback(() => setDocsOpen(false), []);
  const closeDebug = useCallback(() => setDebugOpen(false), []);
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

  const handleOpenSettings = useCallback(() => {
    setDocsOpen(false);
    openSettings();
  }, [openSettings]);

  const handleOpenDocuments = useCallback(() => {
    if (settingsOpen) closeSettings();
    setDocsOpen(true);
  }, [settingsOpen, closeSettings]);

  return (
    <div className="flex flex-col w-full h-full bg-background overflow-hidden">
      {!isFullscreen && <div className="h-7 shrink-0" data-tauri-drag-region />}
      <Header
        onDocumentsOpen={handleOpenDocuments}
        onSettingsOpen={handleOpenSettings}
        onDebugOpen={() => setDebugOpen(true)}
      />

      <div className="flex flex-1 overflow-hidden">
        <LeftSidebar onOpenSettings={handleOpenSettings} />
        <div className="flex-1 flex flex-col relative w-full min-w-0 min-h-0">
          {activeTab === "tools" ? (
            <ToolsPanel />
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
        <SystemSidebar onOpenDocuments={handleOpenDocuments} />
      </div>

      <StatusBar />

      {settingsOpen && (
        <Suspense fallback={null}>
          <SettingsPanel />
        </Suspense>
      )}
      {docsOpen && (
        <Suspense fallback={null}>
          <DocumentsPanel isOpen={docsOpen} onClose={closeDocs} />
        </Suspense>
      )}
      {debugOpen && <TimeTravelView onClose={closeDebug} />}
    </div>
  );
}
