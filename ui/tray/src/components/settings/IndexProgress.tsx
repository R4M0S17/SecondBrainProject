import { useEffect, useState } from "react";
import { getIndexStatus } from "../../api/client";
import { useSettingsStore } from "../../stores/settings";
import type { IndexStatusResponse } from "../../api/types";

export default function IndexProgress() {
  const activeJobId = useSettingsStore((s) => s.activeJobId);
  const clearIndexJob = useSettingsStore((s) => s.clearIndexJob);
  const [status, setStatus] = useState<IndexStatusResponse | null>(null);

  useEffect(() => {
    if (!activeJobId) {
      setStatus(null);
      return;
    }
    let active = true;
    const poll = async () => {
      try {
        const s = await getIndexStatus(activeJobId);
        if (!active) return;
        setStatus(s);
        if (s.status === "running") {
          setTimeout(poll, 1000);
        } else {
          clearIndexJob();
        }
      } catch {
        // ignore
      }
    };
    void poll();
    return () => { active = false; };
  }, [activeJobId, clearIndexJob]);

  if (!status || status.status !== "running") return null;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[11px] text-outline">
        <span>Indexing…</span>
        {status.files_indexed > 0 && (
          <span>{status.files_indexed} files</span>
        )}
      </div>
      <div className="h-[2px] bg-surface-container rounded-full overflow-hidden">
        <div className="h-full bg-primary-container animate-pulse w-full" />
      </div>
    </div>
  );
}
