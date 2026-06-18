interface ToggleSwitchProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  size?: "sm" | "md";
  ariaLabel?: string;
  className?: string;
  knobClassName?: string;
}

export default function ToggleSwitch({
  enabled,
  onChange,
  size = "md",
  ariaLabel,
  className = "",
  knobClassName = "",
}: ToggleSwitchProps) {
  return (
    <button
      role="switch"
      aria-checked={enabled}
      aria-label={ariaLabel}
      onClick={() => onChange(!enabled)}
      className={`relative rounded-full transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary-container shrink-0 ${
        size === "md" ? "w-8 h-4" : "w-7 h-3.5"
      } ${enabled ? "bg-primary-container" : className}`}
    >
      <div
        className={`absolute bg-white rounded-full transition-transform ${
          size === "md" ? "top-0.5 w-3 h-3" : "top-[1px] w-[10px] h-[10px]"
        } ${
          size === "md"
            ? enabled
              ? "translate-x-4 left-0.5"
              : "translate-x-0 left-0.5"
            : enabled
              ? "translate-x-[14px] left-0.5"
              : "translate-x-0 left-0.5"
        } ${knobClassName}`}
      />
    </button>
  );
}
