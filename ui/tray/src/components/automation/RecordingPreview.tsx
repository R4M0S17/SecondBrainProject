import type { RecordingPreviewEvent } from "../../api/types";

interface RecordingPreviewProps {
  events: RecordingPreviewEvent[];
}

function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function RecordingPreview({ events }: RecordingPreviewProps) {
  if (events.length === 0) {
    return (
      <div className="px-4 py-6 text-[12px] text-outline text-center">
        —
      </div>
    );
  }

  return (
    <div className="max-h-40 overflow-y-auto scrollbar-auto px-4 py-2 space-y-1">
      {events.map((ev, i) => (
        <div key={`${ev.timestamp}-${i}`} className="flex gap-3 text-[12px] font-mono">
          <span className="text-outline shrink-0">{formatTime(ev.timestamp)}</span>
          <span className="text-primary-container/80 shrink-0">[{ev.app}]</span>
          <span className="text-on-surface-variant truncate">{ev.detail}</span>
        </div>
      ))}
    </div>
  );
}
