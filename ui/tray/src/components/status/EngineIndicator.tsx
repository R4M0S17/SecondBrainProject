interface EngineIndicatorProps {
  ok: boolean;
  provider?: string;
}

export default function EngineIndicator({ ok, provider }: EngineIndicatorProps) {
  if (provider === "claude") {
    return (
      <div className="flex items-center gap-1">
        <div className="w-[6px] h-[6px] rounded-full bg-[#a78bfa]" />
        <span className="text-[#a78bfa]">Claude API</span>
      </div>
    );
  }

  const label = provider === "mlx" ? "MLX" : "llama.cpp";
  return (
    <div className="flex items-center gap-1">
      <div
        className={`w-[6px] h-[6px] rounded-full ${
          ok ? "bg-[#4ade80]" : "bg-[#ffb4ab]"
        }`}
      />
      <span className={ok ? "text-[#4ade80]" : "text-[#ffb4ab]"}>
        {ok ? `${label} OK` : `${label} down`}
      </span>
    </div>
  );
}
