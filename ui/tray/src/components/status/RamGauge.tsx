interface RamGaugeProps {
  used: number;
  total: number;
  /** From `/api/status` — overrides ratio-based colouring when set. */
  ramPressure?: "ok" | "warn" | "critical";
  onApplyLiteProfile?: () => Promise<void>;
}

export default function RamGauge({
  used,
  total,
  ramPressure = "ok",
  onApplyLiteProfile,
}: RamGaugeProps) {
  const ratio = total > 0 ? used / total : 0;
  const pressureColor =
    ramPressure === "critical"
      ? "text-[#ffb4ab]"
      : ramPressure === "warn"
        ? "text-[#fbbf24]"
        : ratio > 0.9
          ? "text-[#ffb4ab]"
          : ratio > 0.75
            ? "text-[#fbbf24]"
            : "";

  const showLiteHint =
    (ramPressure === "warn" || ramPressure === "critical") && onApplyLiteProfile;

  return (
    <span className={`relative inline-flex items-center group ${pressureColor}`}>
      <span>
        RAM {used.toFixed(1)} / {total.toFixed(1)} GB
      </span>
      {showLiteHint ? (
        <span className="absolute bottom-full left-1/2 z-50 mb-1 hidden w-[240px] -translate-x-1/2 flex-col gap-2 rounded border border-[#242736] bg-[#1c1b23] p-2 normal-case shadow-lg group-hover:flex">
          <span className="text-[10px] leading-snug text-[#c9c4d7]">
            Cerebro is approaching the 8 GB limit. Switch to lite profile.
          </span>
          <button
            type="button"
            className="rounded bg-[#6366f1] px-2 py-1 text-[10px] font-semibold text-white hover:opacity-90"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              void onApplyLiteProfile();
            }}
          >
            Use 8 GB safe profile
          </button>
        </span>
      ) : null}
    </span>
  );
}
