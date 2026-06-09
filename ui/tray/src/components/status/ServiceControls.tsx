import { useServicesStore } from "../../stores/services";

export default function ServiceControls() {
  const { starting, stopping, servicesOff, error, turnOn, turnOff, clearError } =
    useServicesStore();

  const busy = starting || stopping;

  return (
    <div className="flex items-center gap-1 shrink-0 normal-case tracking-normal">
      <button
        type="button"
        disabled={busy || !servicesOff}
        onClick={() => {
          clearError();
          void turnOn();
        }}
        className="px-3 py-1 text-xs font-medium rounded bg-success-green/15 text-success-green border border-success-green/30 hover:bg-success-green/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        title="Start llama engine and Cerebro API"
      >
        {starting ? "Starting…" : "Turn on"}
      </button>
      <button
        type="button"
        disabled={busy || servicesOff}
        onClick={() => {
          clearError();
          void turnOff();
        }}
        className="px-3 py-1 text-xs font-medium rounded bg-error/15 text-error border border-error/30 hover:bg-error/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        title="Stop llama engine and Cerebro API"
      >
        {stopping ? "Stopping…" : "Turn off"}
      </button>
      {error ? (
        <span className="text-error normal-case max-w-[150px] truncate text-xs" title={error}>
          {error}
        </span>
      ) : null}
    </div>
  );
}
