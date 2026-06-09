import { useState, useEffect } from "react";

interface TypingIndicatorProps {
  model?: string;
}

export default function TypingIndicator({ model = "local" }: TypingIndicatorProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setElapsed((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;

  return (
    <div className="flex flex-col gap-3" aria-live="polite" aria-label="Assistant is thinking">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-[2px]">
          <div className="w-[4px] h-[4px] bg-primary-container rounded-full typing-dot" />
          <div className="w-[4px] h-[4px] bg-primary-container rounded-full typing-dot" />
          <div className="w-[4px] h-[4px] bg-primary-container rounded-full typing-dot" />
        </div>
        <div className="flex items-center gap-2">
          <span className="italic text-on-surface-variant text-sm">
            Thinking with {model}
          </span>
          <span className="text-outline text-xs tabular-nums">
            {minutes > 0 ? `${minutes}m ` : ""}{seconds}s
          </span>
        </div>
      </div>
      <div className="w-full h-[2px] bg-outline-variant/30 rounded overflow-hidden">
        <div className="h-full bg-primary-container rounded progress-indeterminate" />
      </div>
    </div>
  );
}
