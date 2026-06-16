import { useEffect, useState } from "react";

interface WarningToastProps {
  message: string;
  onDismiss?: () => void;
}

export default function WarningToast({ message, onDismiss }: WarningToastProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const id = setTimeout(() => {
      setVisible(false);
      onDismiss?.();
    }, 6000);
    return () => clearTimeout(id);
  }, [onDismiss]);

  if (!visible) return null;

  return (
    <div
      role="alert"
      className="flex items-start gap-2 bg-tertiary-fixed-dim/10 border border-tertiary-fixed-dim/30 rounded px-3 py-2 text-[12px] text-tertiary-fixed-dim"
    >
      <svg className="w-4 h-4 shrink-0 mt-[1px]" viewBox="0 0 24 24" fill="currentColor">
        <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
      </svg>
      <span className="flex-1">{message}</span>
      <button
        onClick={() => { setVisible(false); onDismiss?.(); }}
        className="hover:opacity-70 transition-opacity"
        aria-label="Dismiss warning"
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
