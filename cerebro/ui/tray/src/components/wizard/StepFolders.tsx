import { useCallback, useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { getStatus, wizardReprobeCalendarPermission } from "../../api/client";

const MACOS_AUTOMATION_URL =
  "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation";

interface StepFoldersProps {
  onReady: (ready: boolean, folders: string[]) => void;
}

export default function StepFolders({ onReady }: StepFoldersProps) {
  const [folders, setFolders] = useState<string[]>([]);
  const [calendarPerm, setCalendarPerm] = useState<string | null>(null);
  const [reprobeBusy, setReprobeBusy] = useState(false);

  const refreshCalendarPerm = useCallback(async () => {
    try {
      const s = await getStatus();
      setCalendarPerm(s.macos_permissions?.calendar ?? "unknown");
    } catch {
      setCalendarPerm(null);
    }
  }, []);

  useEffect(() => {
    void refreshCalendarPerm();
  }, [refreshCalendarPerm]);

  const openAutomationSettings = async () => {
    try {
      const { open: openUrl } = await import("@tauri-apps/plugin-shell");
      await openUrl(MACOS_AUTOMATION_URL);
    } catch {
      window.alert(
        "Open System Settings → Privacy & Security → Automation, then enable Calendar for the app that runs Python.\n\n" +
          `Or run in Terminal:\nopen '${MACOS_AUTOMATION_URL}'`,
      );
    }
  };

  const handleGrantedClick = async () => {
    setReprobeBusy(true);
    try {
      const { calendar } = await wizardReprobeCalendarPermission();
      setCalendarPerm(calendar);
    } catch {
      await refreshCalendarPerm();
    } finally {
      setReprobeBusy(false);
    }
  };

  const addFolders = async () => {
    try {
      const selected = await open({
        directory: true,
        multiple: true,
        title: "Select folders to watch",
      });
      if (!selected) return;
      const paths = Array.isArray(selected) ? selected : [selected];
      const merged = Array.from(new Set([...folders, ...paths]));
      setFolders(merged);
      onReady(merged.length > 0, merged);
    } catch {
      // user cancelled dialog
    }
  };

  const removeFolder = (path: string) => {
    const next = folders.filter((f) => f !== path);
    setFolders(next);
    onReady(next.length > 0, next);
  };

  const showCalendarCard =
    calendarPerm !== null &&
    calendarPerm !== "ok" &&
    calendarPerm !== "not_macos";

  return (
    <div className="w-full space-y-3 mb-6">
      <p className="text-[14px] text-[#e8eaf0] text-center leading-relaxed">
        Choose the folders Cerebro will index and keep in memory. You can change
        these later in Settings.
      </p>

      {showCalendarCard && (
        <div className="rounded-[6px] border border-[#4a3f2e] bg-[#2a2419] px-3 py-3 space-y-2">
          <p className="text-[13px] text-[#f5e6c8] text-center leading-snug">
            Cerebro needs <strong className="font-semibold">Calendar Automation</strong>{" "}
            permission so calendar questions return real events (not empty guesses).
          </p>
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={() => void openAutomationSettings()}
              className="w-full py-2 rounded-[6px] text-[12px] font-medium bg-[#3d3428] text-[#f5e6c8] hover:bg-[#4d4336] transition-colors"
            >
              Open Settings
            </button>
            <button
              type="button"
              disabled={reprobeBusy}
              onClick={() => void handleGrantedClick()}
              className="w-full py-2 rounded-[6px] text-[12px] font-medium border border-[#5c5244] text-[#c4b8a8] hover:bg-[#332c22] transition-colors disabled:opacity-50"
            >
              {reprobeBusy ? "Checking…" : "I granted it — check again"}
            </button>
          </div>
          <p className="text-[10px] text-[#8b7f6a] text-center">
            Current status: <span className="font-mono">{calendarPerm}</span>
          </p>
        </div>
      )}

      {/* Folder list */}
      {folders.length > 0 && (
        <div className="space-y-1">
          {folders.map((f) => (
            <div
              key={f}
              className="flex items-center justify-between bg-[#242736] px-3 py-2 rounded-[6px] group"
            >
              <div className="flex items-center gap-2 overflow-hidden">
                <svg className="w-4 h-4 text-[#928ea0] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                </svg>
                <span className="font-mono text-[13px] text-[#e5e0ed] truncate">{f}</span>
              </div>
              <button
                onClick={() => removeFolder(f)}
                className="text-[#8b8fa8] hover:text-[#ffb4ab] ml-2 shrink-0 transition-colors"
                aria-label={`Remove ${f}`}
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add folder button */}
      <button
        onClick={addFolders}
        className="w-full py-2 border border-dashed border-[#242736] rounded-[6px] text-[12px] text-[#8b8fa8] hover:bg-[#201f27] transition-colors flex items-center justify-center gap-1"
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M12 5v14M5 12h14" />
        </svg>
        Add Folder
      </button>

      {folders.length === 0 && (
        <p className="text-[11px] text-[#8b8fa8] text-center">
          At least one folder is required to continue.
        </p>
      )}
    </div>
  );
}
