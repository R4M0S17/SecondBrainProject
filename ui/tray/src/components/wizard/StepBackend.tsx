import { useWizardStore } from "../../stores/wizard";

interface StepBackendProps {
  onReady: (ready: boolean) => void;
}

export default function StepBackend({ onReady }: StepBackendProps) {
  const { mode, setMode } = useWizardStore();

  const pick = (m: "local" | "claude") => {
    setMode(m);
    onReady(true);
  };

  return (
    <div className="w-full space-y-3 mb-6">
      <p className="text-[14px] leading-[20px] text-[#e8eaf0] text-center">
        Choose how Cerebro runs inference.
      </p>

      <button
        onClick={() => pick("local")}
        className={`w-full p-4 rounded-lg border text-left transition-colors ${
          mode === "local"
            ? "border-primary-container bg-[#1a2030]"
            : "border-outline-variant bg-background hover:border-outline"
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <div className={`w-2 h-2 rounded-full ${mode === "local" ? "bg-success-green" : "bg-outline"}`} />
          <span className="text-[14px] font-semibold text-on-surface">Local · llama.cpp</span>
        </div>
        <p className="text-[12px] text-outline pl-4">
          Runs entirely on-device. Private. Requires 4–8 GB RAM.
        </p>
      </button>

      <button
        onClick={() => pick("claude")}
        className={`w-full p-4 rounded-lg border text-left transition-colors ${
          mode === "claude"
            ? "border-[#a78bfa] bg-[#1a1030]"
            : "border-outline-variant bg-background hover:border-outline"
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <div className={`w-2 h-2 rounded-full ${mode === "claude" ? "bg-[#a78bfa]" : "bg-outline"}`} />
          <span className="text-[14px] font-semibold text-on-surface">Cloud · Claude API</span>
        </div>
        <p className="text-[12px] text-outline pl-4">
          Anthropic's frontier models. 200K context. Requires{" "}
          <code className="text-[#a78bfa] bg-[#1a1030] px-1 rounded">ANTHROPIC_API_KEY</code>.
        </p>
      </button>
    </div>
  );
}
