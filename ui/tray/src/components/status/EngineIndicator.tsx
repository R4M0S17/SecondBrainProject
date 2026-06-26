import { useTranslation } from "react-i18next";

interface EngineIndicatorProps {
  ok: boolean;
  provider?: string;
  llamaServer?: "up" | "restarting" | "down" | null;
  backendReady?: boolean;
  engineState?: "active" | "suspended" | "unknown";
}

export default function EngineIndicator({
  ok,
  provider,
  llamaServer,
  backendReady = true,
  engineState,
}: EngineIndicatorProps) {
  const { t } = useTranslation();

  if (!backendReady) {
    return (
      <div className="flex items-center gap-1">
        <div className="w-[6px] h-[6px] rounded-full bg-error" />
        <span className="text-error">{t("status.backend_offline")}</span>
      </div>
    );
  }

  if (provider === "claude") {
    return (
      <div className="engine-claude flex items-center gap-1">
        <div className="w-[6px] h-[6px] rounded-full bg-[#a78bfa]" />
        <span className="text-[#a78bfa]">{t("status.claude_api")}</span>
      </div>
    );
  }

  const label = provider === "mlx" ? "MLX" : "llama.cpp";

  if (provider === "mlx") {
    return (
      <div className="flex items-center gap-1">
        <div className={`w-[6px] h-[6px] rounded-full ${ok ? "bg-success-green" : "bg-tertiary-fixed-dim"}`} />
        <span className={ok ? "text-success-green" : "text-outline"}>
          {label} {ok ? t("status.engine_ok") : t("status.engine_off")}
        </span>
      </div>
    );
  }

  if (!ok && llamaServer !== "restarting") {
    return (
      <div className="flex items-center gap-1">
        <div className="w-[6px] h-[6px] rounded-full bg-outline" />
        <span className="text-outline">{t("status.engine_off")}</span>
      </div>
    );
  }

  if (engineState === "suspended") {
    return (
      <div className="flex items-center gap-1">
        <div className="w-[6px] h-[6px] rounded-full bg-[#60a5fa] opacity-60" />
        <span className="text-[#60a5fa] opacity-60">
          {label} {t("status.engine_suspended")}
        </span>
      </div>
    );
  }

  if (llamaServer === "restarting") {
    return (
      <div className="flex items-center gap-1">
        <div className="w-[6px] h-[6px] rounded-full bg-tertiary-fixed-dim animate-pulse" />
        <span className="text-tertiary-fixed-dim">
          {label} {t("status.engine_restarting")}
        </span>
      </div>
    );
  }

  const isUp = llamaServer === "up" || (llamaServer == null && ok);
  return (
    <div className="flex items-center gap-1">
      <div
        className={`w-[6px] h-[6px] rounded-full ${
          isUp ? "bg-success-green" : "bg-error"
        }`}
      />
      <span className={isUp ? "text-success-green" : "text-error"}>
        {label} {isUp ? t("status.engine_ok") : t("status.engine_down")}
      </span>
    </div>
  );
}
