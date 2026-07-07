import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { StandaloneRecordingOverlay } from "./components/automation/RecordingOverlay";
import "./index.css";
import "./i18n";

async function getWindowLabel(): Promise<string> {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    return getCurrentWindow().label;
  } catch {
    return "main";
  }
}

getWindowLabel().then((label) => {
  const root = document.getElementById("root")!;
  if (label === "recording-overlay") {
    document.documentElement.style.background = "transparent";
    document.body.style.background = "transparent";
    document.body.style.overflow = "hidden";
    document.body.style.borderRadius = "16px";
    root.style.width = "100%";
    root.style.height = "100%";
    root.style.overflow = "hidden";
    root.style.borderRadius = "16px";
    ReactDOM.createRoot(root).render(
      <React.StrictMode>
        <StandaloneRecordingOverlay />
      </React.StrictMode>
    );
  } else {
    ReactDOM.createRoot(root).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    );
  }
});
