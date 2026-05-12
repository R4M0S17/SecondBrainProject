import { useEffect, useRef, useState } from "react";
import { useSystemStore } from "../../stores/system";
import { getFleetModels } from "../../api/client";
import type { FleetModelEntry } from "../../api/types";

interface FleetPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function FleetPanel({ open, onClose }: FleetPanelProps) {
  const fleetStatus = useSystemStore((s) => s.fleetStatus);
  const [models, setModels] = useState<FleetModelEntry[]>([]);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    getFleetModels()
      .then((r) => setModels(r.models))
      .catch(() => {});
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open || !fleetStatus) return null;

  const { current_model: cm, hardware: hw } = fleetStatus;
  const ramUsed = hw.ram_total_gb - hw.ram_available_gb;
  const vramUsed = hw.gpu_vram_total_gb - hw.gpu_vram_available_gb;
  const ramRatio = hw.ram_total_gb > 0 ? ramUsed / hw.ram_total_gb : 0;
  const vramRatio = hw.gpu_vram_total_gb > 0 ? vramUsed / hw.gpu_vram_total_gb : 0;

  const gaugeColor = (ratio: number) =>
    ratio > 0.9 ? "bg-[#ffb4ab]" : ratio > 0.75 ? "bg-[#fbbf24]" : "bg-[#4ade80]";

  const backendLabel: Record<string, string> = { metal: "Metal", cuda: "CUDA", none: "CPU" };

  return (
    <>
      {/* Click-outside backdrop */}
      <div className="fixed inset-0 z-40" onClick={onClose} aria-hidden="true" />

      {/* Panel */}
      <div
        ref={panelRef}
        className="fixed bottom-[28px] left-0 z-50 w-[300px] max-h-[400px] overflow-y-auto bg-[#1a1d27] border border-[#242736] rounded-tr-[8px] shadow-2xl custom-scrollbar"
        role="dialog"
        aria-label="Fleet status"
      >
        {/* Active model */}
        <section className="px-4 pt-4 pb-3 border-b border-[#242736]">
          <p className="text-[10px] font-bold tracking-[0.05em] uppercase text-[#8b8fa8] mb-2">
            Active Model
          </p>
          <div className="space-y-1 font-mono text-[11px] text-[#c9c4d7]">
            {[
              ["Name", cm.id],
              ["Family", cm.family],
              ["Params", `${cm.params_b}B`],
              ["Quant", cm.quant],
              ["Context", `${cm.context_length.toLocaleString()} tok`],
              ["GPU Layers", String(cm.gpu_layers)],
              ["Speed", `${cm.speed_tokens_per_sec} tok/s`],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between">
                <span className="text-[#8b8fa8]">{label}</span>
                <span>{value}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Hardware */}
        <section className="px-4 py-3 border-b border-[#242736]">
          <p className="text-[10px] font-bold tracking-[0.05em] uppercase text-[#8b8fa8] mb-2">
            Hardware
          </p>
          <div className="space-y-2">
            <MiniGauge label="RAM" used={ramUsed} total={hw.ram_total_gb} ratio={ramRatio} color={gaugeColor(ramRatio)} />
            {hw.unified_memory ? (
              <div className="font-mono text-[10px] text-[#8b8fa8]">GPU — Unified Memory</div>
            ) : (
              <MiniGauge label="VRAM" used={vramUsed} total={hw.gpu_vram_total_gb} ratio={vramRatio} color={gaugeColor(vramRatio)} />
            )}
            <div className="flex items-center justify-between font-mono text-[10px]">
              <span className="text-[#8b8fa8]">Backend</span>
              <span className="px-1.5 py-0.5 bg-[#242736] rounded text-[#c9c4d7]">
                {backendLabel[hw.gpu_backend] ?? hw.gpu_backend}
              </span>
            </div>
          </div>
        </section>

        {/* Selection rationale */}
        <section className="px-4 py-3 border-b border-[#242736]">
          <p className="text-[10px] font-bold tracking-[0.05em] uppercase text-[#8b8fa8] mb-1">
            Selection
          </p>
          <p className="text-[11px] text-[#8b8fa8] leading-[16px]">
            {fleetStatus.selection_rationale}
          </p>
        </section>

        {/* Available models */}
        {models.length > 0 && (
          <section className="px-4 py-3">
            <p className="text-[10px] font-bold tracking-[0.05em] uppercase text-[#8b8fa8] mb-2">
              Available Models
            </p>
            <ul className="space-y-1">
              {models.map((m) => (
                <li
                  key={m.id}
                  className={`flex items-center justify-between font-mono text-[10px] rounded px-1.5 py-1 ${
                    m.id === cm.id ? "bg-[#242736] text-[#e5e0ed]" : "text-[#8b8fa8]"
                  }`}
                >
                  <span className="flex items-center gap-1.5">
                    {!m.available_on_disk && (
                      <svg
                        className="w-2.5 h-2.5 text-[#fbbf24] shrink-0"
                        viewBox="0 0 24 24"
                        fill="currentColor"
                      >
                        <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
                      </svg>
                    )}
                    <span>{m.id}</span>
                  </span>
                  <span className="text-[#474554]">{m.quant}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </>
  );
}

function MiniGauge({ label, used, total, ratio, color }: {
  label: string;
  used: number;
  total: number;
  ratio: number;
  color: string;
}) {
  return (
    <div>
      <div className="flex justify-between font-mono text-[10px] text-[#c9c4d7] mb-1">
        <span>{label}</span>
        <span>{used.toFixed(1)} / {total} GB</span>
      </div>
      <div className="h-1 bg-[#242736] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${Math.min(ratio * 100, 100)}%` }}
        />
      </div>
    </div>
  );
}
