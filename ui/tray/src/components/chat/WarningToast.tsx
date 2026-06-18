import { useState } from "react";
import Toast from "../shared/Toast";

interface WarningToastProps {
  message: string;
  onDismiss?: () => void;
}

export default function WarningToast({ message, onDismiss }: WarningToastProps) {
  const [visible, setVisible] = useState(true);

  const handleDismiss = () => {
    setVisible(false);
    onDismiss?.();
  };

  return (
    <Toast
      visible={visible}
      onDismiss={handleDismiss}
      duration={6000}
      dismissLabel="Dismiss warning"
      className="bg-tertiary-fixed-dim/10 border border-tertiary-fixed-dim/30 text-tertiary-fixed-dim"
    >
      <svg className="w-4 h-4 shrink-0 mt-[1px]" viewBox="0 0 24 24" fill="currentColor">
        <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
      </svg>
      <span className="flex-1">{message}</span>
    </Toast>
  );
}
