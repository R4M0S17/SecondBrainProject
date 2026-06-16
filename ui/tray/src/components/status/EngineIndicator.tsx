interface EngineIndicatorProps {
  ok: boolean;
  provider?: string;
  llamaServer?: "up" | "restarting" | "down" | null;
  servicesOff?: boolean;
  engineState?: "active" | "suspended" | "unknown";
}

export default function EngineIndicator({
  ok,
  provider,
  llamaServer,
  servicesOff,
  engineState,
}: EngineIndicatorProps) {
  if (servicesOff) {
    return (
      <div className="flex items-center gap-1">
        <div className="w-[6px] h-[6px] rounded-full bg-outline" />
        <span className="text-outline">Turned off</span>
      </div>
    );
  }
  if (provider === "claude") {
    return (
      <div className="engine-claude flex items-center gap-1">
        <div className="w-[6px] h-[6px] rounded-full bg-[#a78bfa]" />
        <span className="text-[#a78bfa]">Claude API</span>
      </div>
    );
  }

  const label = provider === "mlx" ? "MLX" : "llama.cpp";

  if (engineState === "suspended") {
    return (
      <div className="flex items-center gap-1">
        <div className="w-[6px] h-[6px] rounded-full bg-[#60a5fa] opacity-60" />
        <span className="text-[#60a5fa] opacity-60">{label} suspended</span>
      </div>
    );
  }

  if (llamaServer === "restarting") {
    return (
      <div className="flex items-center gap-1">
        <div className="w-[6px] h-[6px] rounded-full bg-tertiary-fixed-dim animate-pulse" />
        <span className="text-tertiary-fixed-dim">{label} restarting</span>
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
        {isUp ? `${label} OK` : `${label} down`}
      </span>
    </div>
  );
}
