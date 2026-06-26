import { useState, useRef, type ReactNode } from "react";

interface TooltipProps {
  content: string;
  children: ReactNode;
  side?: "right" | "top";
  delay?: number;
}

export default function Tooltip({ content, children, side = "right", delay = 300 }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setVisible(true), delay);
  };
  const hide = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setVisible(false);
  };

  return (
    <div className="relative" onMouseEnter={show} onMouseLeave={hide} onFocus={show} onBlur={hide}>
      {children}
      {visible && (
        <div
          className={`
            absolute pointer-events-none whitespace-nowrap z-50
            px-3 py-1.5 rounded-lg text-label-caps
            bg-surface-container-high/90 backdrop-blur-xl
            border border-outline-variant/20
            text-on-surface shadow-lg
            animate-tooltip-in
            ${side === "right" ? "left-full ml-2 top-1/2 -translate-y-1/2" : ""}
            ${side === "top" ? "bottom-full mb-2 left-1/2 -translate-x-1/2" : ""}
          `}
          role="tooltip"
        >
          <span
            className={`
              absolute w-2 h-2 bg-surface-container-high/90 border-outline-variant/20
              ${side === "right"
                ? "-left-1 top-1/2 -translate-y-1/2 rotate-45 border-l border-b"
                : "-bottom-1 left-1/2 -translate-x-1/2 rotate-45 border-r border-b"
              }
            `}
          />
          {content}
        </div>
      )}
    </div>
  );
}
