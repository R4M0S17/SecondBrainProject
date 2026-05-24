interface EngineIndicatorProps {
  ok: boolean;
  provider?: string;
  llamaServer?: "up" | "restarting" | "down" | null;
}

export default function EngineIndicator({ ok, provider, llamaServer }: EngineIndicatorProps) {
  if (provider === "claude") {
    return (
      <div className="engine-claude flex items-center gap-1">
        <div className="w-[6px] h-[6px] rounded-full bg-[#a78bfa]" />
        <span className="text-[#a78bfa]">Claude API</span>
      </div>
    );
  }

  const label = provider === "mlx" ? "MLX" : "llama.cpp";

  if (llamaServer === "restarting") {
    return (
      <div className="flex items-center gap-1">
        <div className="w-[6px] h-[6px] rounded-full bg-[#fbbf24] animate-pulse" />
        <span className="text-[#fbbf24]">{label} restarting</span>
      </div>
    );
  }

  const isUp = llamaServer === "up" || (llamaServer == null && ok);
  return (
    <div className="flex items-center gap-1">
      <div
        className={`w-[6px] h-[6px] rounded-full ${
          isUp ? "bg-[#4ade80]" : "bg-[#ffb4ab]"
        }`}
      />
      <span className={isUp ? "text-[#4ade80]" : "text-[#ffb4ab]"}>
        {isUp ? `${label} OK` : `${label} down`}
      </span>
    </div>
  );
}
