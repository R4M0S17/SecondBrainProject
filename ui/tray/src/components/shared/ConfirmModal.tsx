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
      className="fixed inset-0 bg-black/60 backdrop-blur-[4px] z-[70] flex items-center justify-center p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-modal-title"
    >
      <div className="w-[400px] bg-surface-container rounded-xl border border-outline-variant shadow-2xl overflow-hidden">
        <div className="p-5 space-y-4">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-[22px] text-tertiary-fixed-dim">warning</span>
            <span
              id="confirm-modal-title"
              className="text-on-surface text-[15px] font-semibold"
            >
              Tool requires your approval
            </span>
          </div>

          <div className="bg-background rounded-lg p-4 border border-outline-variant space-y-3">
            <div className="flex items-start gap-3">
              <span className="text-[10px] font-bold tracking-wider uppercase text-outline pt-0.5 w-12 shrink-0">Tool</span>
              <span className="font-mono text-[13px] text-primary-container break-all">{toolName}</span>
            </div>
            {toolPath && (
              <div className="flex items-start gap-3">
                <span className="text-[10px] font-bold tracking-wider uppercase text-outline pt-0.5 w-12 shrink-0">Path</span>
                <span className="font-mono text-[13px] text-on-surface break-all">{toolPath}</span>
              </div>
            )}
            <div className="flex items-start gap-3">
              <span className="text-[10px] font-bold tracking-wider uppercase text-outline pt-0.5 w-12 shrink-0">Action</span>
              <div>
                <span className="font-mono text-[13px] text-on-surface">{toolAction}</span>
                {toolSize && (
                  <span className="font-mono text-[12px] text-outline ml-2">({toolSize})</span>
                )}
              </div>
            </div>
          </div>

          <p className="text-[13px] text-outline leading-relaxed">{warningText}</p>
        </div>

        <div className="flex gap-3 px-5 pb-5">
          <button
            onClick={onDeny}
            className="flex-1 h-10 rounded-lg border border-outline-variant text-on-surface-variant text-sm font-medium hover:bg-surface-container-high transition-colors active:opacity-80"
          >
            Deny
          </button>
          <button
            onClick={onApprove}
            className="flex-1 h-10 rounded-lg bg-primary-container text-on-primary-container text-sm font-semibold hover:brightness-110 transition-all active:opacity-80 flex items-center justify-center gap-1.5"
          >
            <span className="material-symbols-outlined text-[16px]">check</span>
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
