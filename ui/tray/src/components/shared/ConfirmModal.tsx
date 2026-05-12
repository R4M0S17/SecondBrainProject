interface ConfirmModalProps {
  toolName: string;
  toolPath?: string;
  toolAction?: string;
  toolSize?: string;
  warningText?: string;
  onApprove: () => void;
  onDeny: () => void;
}

export default function ConfirmModal({
  toolName,
  toolPath,
  toolAction = "Perform action",
  toolSize,
  warningText = "This action will modify your filesystem. It cannot be automatically undone.",
  onApprove,
  onDeny,
}: ConfirmModalProps) {
  return (
    <div
      className="absolute inset-0 bg-black/60 backdrop-blur-[4px] z-50 flex items-center justify-center p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-modal-title"
    >
      {/* Modal card */}
      <div className="w-[380px] bg-[#1a1d27] rounded-[12px] border border-[#242736] p-[28px_24px] shadow-2xl flex flex-col gap-4">
        {/* Header row */}
        <div className="flex items-center gap-3">
          <svg
            className="w-5 h-5 text-[#fbbf24] shrink-0"
            viewBox="0 0 24 24"
            fill="currentColor"
          >
            <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
          </svg>
          <span
            id="confirm-modal-title"
            className="text-[#e8eaf0] text-[15px] font-semibold"
          >
            Tool requires your approval
          </span>
        </div>

        {/* Tool info block */}
        <div className="bg-[#0f1117] rounded p-3 border border-[#242736] space-y-2">
          <div className="flex items-baseline justify-between">
            <span className="text-[11px] font-bold tracking-[0.05em] uppercase text-[#928ea0]">
              Tool
            </span>
            <span className="font-mono text-[12px] text-[#94a3b8]">{toolName}</span>
          </div>
          {toolPath && (
            <div className="flex items-baseline justify-between">
              <span className="text-[11px] font-bold tracking-[0.05em] uppercase text-[#928ea0]">
                Path
              </span>
              <span className="font-mono text-[12px] text-[#e8eaf0]">{toolPath}</span>
            </div>
          )}
          <div className="flex items-baseline justify-between">
            <span className="text-[11px] font-bold tracking-[0.05em] uppercase text-[#928ea0]">
              Action
            </span>
            <div className="text-right">
              <span className="font-mono text-[12px] text-[#e8eaf0]">{toolAction}</span>
              {toolSize && (
                <span className="font-mono text-[12px] text-[#928ea0] block">
                  ({toolSize})
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Warning text */}
        <p className="text-[#8b8fa8] text-[14px] leading-[20px]">{warningText}</p>

        {/* Buttons */}
        <div className="flex gap-3 pt-1">
          <button
            onClick={onDeny}
            className="flex-1 h-10 bg-transparent border border-[#242736] text-[#8b8fa8] text-[16px] font-semibold leading-[24px] rounded transition-colors hover:bg-[#2a2932] active:opacity-80"
          >
            Deny
          </button>
          <button
            onClick={onApprove}
            className="flex-1 h-10 bg-[#94a3b8] text-[#0f1117] text-[16px] font-bold leading-[24px] rounded flex items-center justify-center gap-1 transition-colors hover:brightness-110 active:opacity-80"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path d="M20 6L9 17l-5-5" />
            </svg>
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
