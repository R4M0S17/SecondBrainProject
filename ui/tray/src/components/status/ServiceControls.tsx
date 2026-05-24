import { useServicesStore } from "../../stores/services";
import { useSystemStore } from "../../stores/system";

export default function ServiceControls() {
  const { status, health } = useSystemStore();
  const { starting, stopping, error, turnOn, turnOff, clearError } = useServicesStore();

  const servicesUp = Boolean(status?.engine_ok && health);
  const busy = starting || stopping;

  return (
    <div className="flex items-center gap-1.5 shrink-0 normal-case tracking-normal">
      <button
        type="button"
        disabled={busy || servicesUp}
        onClick={() => {
          clearError();
          void turnOn();
        }}
        className="px-2 py-0.5 rounded border border-[#4ade80]/40 text-[11px] text-[#4ade80] hover:bg-[#4ade80]/10 disabled:opacity-40 disabled:cursor-not-allowed"
        title="Start llama engine and Cerebro API"
      >
        {starting ? "Starting…" : "Turn on"}
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          clearError();
          void turnOff();
        }}
        className="px-2 py-0.5 rounded border border-[#ffb4ab]/40 text-[11px] text-[#ffb4ab] hover:bg-[#ffb4ab]/10 disabled:opacity-40 disabled:cursor-not-allowed"
        title="Stop llama engine and Cerebro API"
      >
        {stopping ? "Stopping…" : "Turn off"}
      </button>
      {error ? (
        <span className="text-[#ffb4ab] normal-case max-w-[200px] truncate" title={error}>
          {error}
        </span>
      ) : null}
    </div>
  );
}
