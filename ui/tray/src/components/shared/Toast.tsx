import { useEffect, useRef } from "react";

interface ToastProps {
  visible: boolean;
  onDismiss: () => void;
  duration?: number;
  children: React.ReactNode;
  className?: string;
  dismissLabel?: string;
}

export default function Toast({
  visible,
  onDismiss,
  duration = 4000,
  children,
  className = "",
  dismissLabel = "Dismiss",
}: ToastProps) {
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    if (visible) {
      timerRef.current = setTimeout(() => {
        onDismiss();
      }, duration);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [visible, duration, onDismiss]);

  if (!visible) return null;

  return (
    <div
      role="alert"
      className={`flex items-start gap-2 rounded-[8px] px-4 py-2.5 text-[13px] font-semibold shadow-lg transition-all duration-300 ${className}`}
    >
      {children}
      <button
        onClick={onDismiss}
        className="ml-auto opacity-70 hover:opacity-100 shrink-0"
        aria-label={dismissLabel}
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
