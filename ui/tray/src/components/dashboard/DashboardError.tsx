interface DashboardErrorProps {
  message: string;
  onRetry: () => void;
}

export default function DashboardError({ message, onRetry }: DashboardErrorProps) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 py-8 gap-4">
      <span className="material-symbols-outlined text-[48px] text-warning-400">
        warning
      </span>
      <p className="text-[15px] font-semibold text-on-surface text-center">Cannot reach backend</p>
      <p className="text-[13px] text-on-surface-variant/60 text-center max-w-md">{message}</p>
      <button
        onClick={onRetry}
        className="px-5 py-2 bg-primary-container text-on-primary-container rounded-lg text-[14px] font-semibold
                   hover:bg-primary-container/80 transition-colors active:scale-[0.97]"
      >
        Retry
      </button>
    </div>
  );
}
