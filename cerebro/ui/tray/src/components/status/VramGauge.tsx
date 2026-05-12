interface VramGaugeProps {
  used: number;
  total: number;
  unified: boolean;
}

export default function VramGauge({ used, total, unified }: VramGaugeProps) {
  if (unified) return null;

  const ratio = total > 0 ? used / total : 0;
  const color =
    ratio > 0.9 ? "text-[#ffb4ab]" : ratio > 0.75 ? "text-[#fbbf24]" : "";

  return (
    <span className={color}>
      VRAM {used.toFixed(1)} / {total} GB
    </span>
  );
}
