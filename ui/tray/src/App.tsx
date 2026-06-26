import { Component, useEffect, type ReactNode, type ErrorInfo } from "react";
import { withTranslation } from "react-i18next";
import { invoke } from "@tauri-apps/api/core";
import { useWizardStore } from "./stores/wizard";
import { useSystemStore } from "./stores/system";
import { useServicesStore } from "./stores/services";
import { useSettingsStore } from "./stores/settings";
import { useDashboardStore } from "./stores/dashboard";
import { getWizardStatus, setApiKey } from "./api/client";
import WizardShell from "./components/wizard/WizardShell";
import MainLayout from "./layouts/MainLayout";

class ErrorBoundaryInner extends Component<
  { children: ReactNode; t: (key: string) => string },
  { hasError: boolean; message: string }
> {
  state: { hasError: boolean; message: string } = { hasError: false, message: "" };

  constructor(props: { children: ReactNode; t: (key: string) => string }) {
    super(props);
  }

  static getDerivedStateFromError(err: Error) {
    return { hasError: true, message: err.message };
  }

  componentDidCatch(_err: Error, _info: ErrorInfo) {}

  render() {
    const { t } = this.props;
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full bg-background text-on-surface gap-4 p-8">
          <p className="text-[16px] font-semibold">{t("app.error_boundary")}</p>
          <p className="text-[12px] text-outline text-center">{this.state.message}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-primary-container text-on-primary-container rounded text-[14px] font-semibold"
          >
            {t("app.reload")}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const ErrorBoundary = withTranslation()(ErrorBoundaryInner);

export default function App() {
  const { isComplete, complete } = useWizardStore();
  const { startPolling, stopPolling } = useSystemStore();
  const { load: loadSettings } = useSettingsStore();

  useEffect(() => {
    void (async () => {
      try {
        const key = await invoke<string | null>("get_cerebro_key");
        if (key) setApiKey(key);
      } catch {
        // API key not available — auth skipped
      }
      await useServicesStore.getState().probeBackend();
      try {
        const status = await getWizardStatus();
        if (!status.is_first_launch) {
          complete();
        }
      } catch {
        // Backend not running — still show main UI
        complete();
      }
      startPolling();
      void loadSettings();
      useDashboardStore.getState().refresh();
    })();

    return () => stopPolling();
  }, [complete, startPolling, stopPolling, loadSettings]);

  return (
    <ErrorBoundary>
      {isComplete ? <MainLayout /> : <WizardShell />}
    </ErrorBoundary>
  );
}
