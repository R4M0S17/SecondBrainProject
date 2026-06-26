import { useTranslation } from "react-i18next";
import { useServicesStore } from "../../stores/services";
import { useSystemStore } from "../../stores/system";
import { needsLocalEngine } from "../../stores/services";

export default function ServiceControls() {
  const { t } = useTranslation();
  const { starting, stopping, backendReady, error, turnOn, turnOff, clearError } =
    useServicesStore();
  const provider = useSystemStore((s) => s.status?.provider);
  const engineOk = useSystemStore((s) => s.status?.engine_ok ?? false);

  const busy = starting || stopping;
  const showEngineControls = needsLocalEngine(provider);

  if (!showEngineControls) {
    return null;
  }

  const canTurnOn = backendReady && !engineOk && !busy;
  const canTurnOff = backendReady && engineOk && !busy;

  return (
    <div className="flex items-center gap-1 shrink-0 normal-case tracking-normal">
      <button
        type="button"
        disabled={!canTurnOn}
        onClick={() => {
          clearError();
          void turnOn();
        }}
        className="px-3 py-1 text-xs font-medium rounded bg-success-green/15 text-success-green border border-success-green/30 hover:bg-success-green/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        title={t("service.turn_on")}
      >
        {starting ? t("service.starting") : t("service.turn_on")}
      </button>
      <button
        type="button"
        disabled={!canTurnOff}
        onClick={() => {
          clearError();
          void turnOff();
        }}
        className="px-3 py-1 text-xs font-medium rounded bg-error/15 text-error border border-error/30 hover:bg-error/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        title={t("service.turn_off")}
      >
        {stopping ? t("service.stopping") : t("service.turn_off")}
      </button>
      {error ? (
        <span className="text-error normal-case max-w-[150px] truncate text-xs" title={error}>
          {error}
        </span>
      ) : null}
    </div>
  );
}
