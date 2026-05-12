import { Component, useEffect, type ReactNode, type ErrorInfo } from "react";
import { useWizardStore } from "./stores/wizard";
import { useSystemStore } from "./stores/system";
import { useSettingsStore } from "./stores/settings";
import { getWizardStatus } from "./api/client";
import WizardShell from "./components/wizard/WizardShell";
import MainLayout from "./layouts/MainLayout";

class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; message: string }
> {
  state: { hasError: boolean; message: string } = { hasError: false, message: "" };

  constructor(props: { children: ReactNode }) {
    super(props);
  }

  static getDerivedStateFromError(err: Error) {
    return { hasError: true, message: err.message };
  }

  componentDidCatch(_err: Error, _info: ErrorInfo) {}

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full bg-[#0f1117] text-[#e5e0ed] gap-4 p-8">
          <p className="text-[16px] font-semibold">Something went wrong in the UI.</p>
          <p className="text-[12px] text-[#8b8fa8] text-center">{this.state.message}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-[#94a3b8] text-[#0f1117] rounded text-[14px] font-semibold"
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const { isComplete, complete } = useWizardStore();
  const { startPolling, stopPolling } = useSystemStore();
  const { load: loadSettings } = useSettingsStore();

  useEffect(() => {
    void (async () => {
      try {
        const status = await getWizardStatus();
        if (!status.is_first_launch) {
          complete();
        }
      } catch {
        // Backend not running — skip wizard in dev
        complete();
      }
      startPolling();
      void loadSettings();
    })();

    return () => stopPolling();
  }, [complete, startPolling, stopPolling, loadSettings]);

  return (
    <ErrorBoundary>
      {isComplete ? <MainLayout /> : <WizardShell />}
    </ErrorBoundary>
  );
}
