import { useState } from "react";
import ServiceControls from "../components/status/ServiceControls";
import TimeTravelView from "../components/debug/TimeTravelView";
import WorkflowPanel from "../components/automation/WorkflowPanel";

interface HeaderProps {
  onDocumentsOpen?: () => void;
  onSettingsOpen?: () => void;
}

export default function Header({ onDocumentsOpen, onSettingsOpen }: HeaderProps) {
  const [debugOpen, setDebugOpen] = useState(false);
  const [workflowsOpen, setWorkflowsOpen] = useState(false);

  return (
    <header
      data-tauri-drag-region
      className="flex justify-between items-center w-full px-4 md:px-margin-desktop h-12 bg-background/80 backdrop-blur-md border-b border-outline-variant/30 z-50 shrink-0"
      role="banner"
    >
      <div className="flex items-center gap-4" data-tauri-drag-region>
        <img src="/BestLogo.svg" alt="Cerebro" className="h-7 w-7 object-contain shrink-0" />
        <span className="text-sm font-bold text-on-surface select-none">
          Cerebro
        </span>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <div className="hidden md:flex gap-1">
          <ServiceControls />
        </div>
        <div className="flex items-center gap-1 text-on-surface-variant">
          <button
            onClick={onDocumentsOpen}
            className="p-1.5 hover:text-primary transition-colors rounded hover:bg-surface-container"
            aria-label="Documents"
            title="Documents"
          >
            <span className="material-symbols-outlined text-[18px]">description</span>
          </button>
          <button
            onClick={onSettingsOpen}
            className="p-1.5 hover:text-primary transition-colors rounded hover:bg-surface-container"
            aria-label="Settings"
            title="Settings (⌘,)"
          >
            <span className="material-symbols-outlined text-[18px]">settings</span>
          </button>
          <button
            onClick={() => setDebugOpen(true)}
            className="p-1.5 hover:text-primary transition-colors rounded hover:bg-surface-container"
            aria-label="History/Debug"
            title="Time-Travel Debugger"
          >
            <span className="material-symbols-outlined text-[18px]">history</span>
          </button>
          <button
            onClick={() => setWorkflowsOpen(true)}
            className="p-1.5 hover:text-primary transition-colors rounded hover:bg-surface-container"
            aria-label="Monitoring"
            title="Desktop Workflows"
          >
            <span className="material-symbols-outlined text-[18px]">monitoring</span>
          </button>
        </div>
      </div>

      {debugOpen && <TimeTravelView onClose={() => setDebugOpen(false)} />}
      {workflowsOpen && <WorkflowPanel onClose={() => setWorkflowsOpen(false)} />}
    </header>
  );
}
