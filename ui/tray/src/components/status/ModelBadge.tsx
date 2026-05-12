interface ModelBadgeProps {
  modelId: string;
  quantization: string;
  swapInProgress: boolean;
  onClick: () => void;
}

function quantColor(quant: string): string {
  const q = quant.toUpperCase();
  if (q.startsWith("Q8")) return "text-[#4ade80]";
  if (q.startsWith("Q4") || q.startsWith("Q5")) return "text-[#fbbf24]";
  if (q.startsWith("Q2") || q.startsWith("Q3")) return "text-[#f97316]";
  return "text-[#c9c4d7]";
}

export default function ModelBadge({ modelId, quantization, swapInProgress, onClick }: ModelBadgeProps) {
  return (
    <button
      onClick={onClick}
      className={[
        "flex items-center gap-1.5 cursor-pointer select-none bg-transparent border-0 p-0",
        "font-mono text-[10px] uppercase tracking-wider text-[#c9c4d7]",
        swapInProgress ? "animate-pulse" : "",
      ].join(" ")}
      title="Fleet status"
    >
      {swapInProgress && (
        <svg
          className="w-2.5 h-2.5 animate-spin shrink-0"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
        </svg>
      )}
      <span>{modelId}</span>
      {quantization && (
        <span className={["px-1 rounded", quantColor(quantization)].join(" ")}>
          {quantization}
        </span>
      )}
    </button>
  );
}
