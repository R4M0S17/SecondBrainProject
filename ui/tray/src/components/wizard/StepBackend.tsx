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
            ? "border-[#94a3b8] bg-[#1a2030]"
            : "border-[#242736] bg-[#0f1117] hover:border-[#474554]"
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <div className={`w-2 h-2 rounded-full ${mode === "local" ? "bg-[#4ade80]" : "bg-[#474554]"}`} />
          <span className="text-[14px] font-semibold text-[#e5e0ed]">Local · llama.cpp</span>
        </div>
        <p className="text-[12px] text-[#8b8fa8] pl-4">
          Runs entirely on-device. Private. Requires 4–8 GB RAM.
        </p>
      </button>

      <button
        onClick={() => pick("claude")}
        className={`w-full p-4 rounded-lg border text-left transition-colors ${
          mode === "claude"
            ? "border-[#a78bfa] bg-[#1a1030]"
            : "border-[#242736] bg-[#0f1117] hover:border-[#474554]"
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <div className={`w-2 h-2 rounded-full ${mode === "claude" ? "bg-[#a78bfa]" : "bg-[#474554]"}`} />
          <span className="text-[14px] font-semibold text-[#e5e0ed]">Cloud · Claude API</span>
        </div>
        <p className="text-[12px] text-[#8b8fa8] pl-4">
          Anthropic's frontier models. 200K context. Requires{" "}
          <code className="text-[#a78bfa] bg-[#1a1030] px-1 rounded">ANTHROPIC_API_KEY</code>.
        </p>
      </button>
    </div>
  );
}
