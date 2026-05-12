import { Suspense, lazy } from "react";
import Header from "./Header";
import ChatWindow from "../components/chat/ChatWindow";
import StatusBar from "../components/status/StatusBar";
import { useSettingsStore } from "../stores/settings";

const SettingsPanel = lazy(() => import("../components/settings/SettingsPanel"));

export default function MainLayout() {
  const { isOpen } = useSettingsStore();

  return (
    <div className="flex flex-col w-full h-full bg-[#0f1117] overflow-hidden">
      <div
        className="h-7 bg-[#1c1b23] shrink-0"
        onMouseDown={() =>
          import("@tauri-apps/api/window")
            .then(({ getCurrentWindow }) => getCurrentWindow().startDragging())
            .catch(() => {})
        }
      />
      <Header />
      <ChatWindow className="flex-1 min-h-0" />
      <StatusBar />
      {isOpen && (
        <Suspense fallback={null}>
          <SettingsPanel />
        </Suspense>
      )}
    </div>
  );
}
