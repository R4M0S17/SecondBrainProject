interface LatencyBadgeProps {
  p95: number;
}

export default function LatencyBadge({ p95 }: LatencyBadgeProps) {
  const color =
    p95 > 15 ? "text-[#ffb4ab]" : p95 > 8 ? "text-[#fbbf24]" : "";

  return <span className={color}>p95 {p95.toFixed(1)}s</span>;
}
