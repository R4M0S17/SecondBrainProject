interface RamGaugeProps {
  used: number;
  total: number;
}

export default function RamGauge({ used, total }: RamGaugeProps) {
  const ratio = total > 0 ? used / total : 0;
  const color =
    ratio > 0.9 ? "text-[#ffb4ab]" : ratio > 0.75 ? "text-[#fbbf24]" : "";

  return (
    <span className={color}>
      RAM {used.toFixed(1)} / {total} GB
    </span>
  );
}
