import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { open } from "@tauri-apps/plugin-dialog";
import { getStatus, wizardReprobeCalendarPermission } from "../../api/client";
import FolderList from "../shared/FolderList";

const MACOS_AUTOMATION_URL =
  "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation";

interface StepFoldersProps {
  onReady: (ready: boolean, folders: string[]) => void;
}

export default function StepFolders({ onReady }: StepFoldersProps) {
  const { t } = useTranslation();
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
      window.alert(`${t("wizard.open_settings")}\n\nOr run in Terminal:\nopen '${MACOS_AUTOMATION_URL}'`);
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
        {t("wizard.folders_desc")}
      </p>

      {showCalendarCard && (
        <div className="rounded-[6px] border border-[#4a3f2e] bg-[#2a2419] px-3 py-3 space-y-2">
          <p className="text-[13px] text-[#f5e6c8] text-center leading-snug">
            {t("wizard.calendar_permission")}: {t("wizard.calendar_desc")}
          </p>
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={() => void openAutomationSettings()}
              className="w-full py-2 rounded-[6px] text-[12px] font-medium bg-[#3d3428] text-[#f5e6c8] hover:bg-[#4d4336] transition-colors"
            >
              {t("wizard.open_settings_btn")}
            </button>
            <button
              type="button"
              disabled={reprobeBusy}
              onClick={() => void handleGrantedClick()}
              className="w-full py-2 rounded-[6px] text-[12px] font-medium border border-[#5c5244] text-[#c4b8a8] hover:bg-[#332c22] transition-colors disabled:opacity-50"
            >
              {reprobeBusy ? t("wizard.calendar_checking") : t("wizard.calendar_granted")}
            </button>
          </div>
          <p className="text-[10px] text-[#8b7f6a] text-center">
            {t("wizard.calendar_status", { perm: calendarPerm ?? "unknown" })}
          </p>
        </div>
      )}

      <FolderList
        folders={folders}
        onAdd={addFolders}
        onRemove={removeFolder}
        minFoldersMessage={t("wizard.folder_required")}
      />
    </div>
  );
}
