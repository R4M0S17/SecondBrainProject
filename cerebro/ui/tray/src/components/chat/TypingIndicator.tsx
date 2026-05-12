interface TypingIndicatorProps {
  model?: string;
}

export default function TypingIndicator({ model = "phi3:mini" }: TypingIndicatorProps) {
  return (
    <div className="flex flex-col gap-2" aria-live="polite" aria-label="Assistant is thinking">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-[2px]">
          <div className="w-[4px] h-[4px] bg-[#94a3b8] rounded-full typing-dot" />
          <div className="w-[4px] h-[4px] bg-[#94a3b8] rounded-full typing-dot" />
          <div className="w-[4px] h-[4px] bg-[#94a3b8] rounded-full typing-dot" />
        </div>
        <span className="italic text-[#c9c4d7] text-[14px] leading-[20px]">
          Thinking with {model}…
        </span>
      </div>
    </div>
  );
}
