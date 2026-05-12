import { useSettingsStore } from "../../stores/settings";
import { useSystemStore, selectIsClaudeMode } from "../../stores/system";
import { CLAUDE_MODELS } from "../../api/types";

const RECOMMENDED: { name: string; ramGb: string; note: string }[] = [
  { name: "phi4-mini:latest", ramGb: "~2.5 GB", note: "Fast & lightweight" },
  { name: "qwen3:4b",         ramGb: "~2.6 GB", note: "Strong reasoning" },
  { name: "qwen3:1.7b",       ramGb: "~1.1 GB", note: "Ultra-lightweight" },
  { name: "llama3.2:3b",      ramGb: "~2.0 GB", note: "Meta · efficient" },
  { name: "gemma3:4b",        ramGb: "~3.3 GB", note: "Google · balanced" },
  { name: "mistral:7b",       ramGb: "~4.1 GB", note: "High quality" },
];

function RadioRow({
  name,
  sub,
  badge,
  isActive,
  onClick,
}: {
  name: string;
  sub: string;
  badge?: string;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`flex items-center justify-between p-2 rounded-[6px] cursor-pointer transition-colors ${
        isActive ? "bg-[#242736] border-l-2 border-[#94a3b8]" : "hover:bg-[#242736]"
      }`}
    >
      <div className="flex items-center gap-2">
        <div
          className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center ${
            isActive ? "border-[#94a3b8]" : "border-[#474554]"
          }`}
        >
          {isActive && <div className="w-1.5 h-1.5 bg-[#94a3b8] rounded-full" />}
        </div>
        <div className="flex flex-col">
          <span className="text-[13px] font-semibold leading-none mb-0.5 text-[#e5e0ed]">
            {name}
          </span>
          <span className="text-[10px] font-mono text-[#c9c4d7]">{sub}</span>
        </div>
      </div>
      {badge && (
        <span className="bg-[#1a1d27] px-1.5 py-0.5 rounded text-[10px] font-mono text-[#c9c4d7]">
          {badge}
        </span>
      )}
    </div>
  );
}

export default function ModelSelector() {
  const { models, activeModel, llamaCppModels, llamaCppLoading, patch } = useSettingsStore();
  const status = useSystemStore((s) => s.status);
  const isCloud = selectIsClaudeMode(status);

  if (isCloud) {
    return (
      <section className="space-y-4">
        <p className="text-[10px] font-mono uppercase tracking-widest text-[#928ea0] mb-1 px-1">
          Cloud · Claude API
        </p>
        <div className="space-y-1">
          {CLAUDE_MODELS.map((m) => (
            <div
              key={m.id}
              className={`flex items-center justify-between p-2 rounded-[6px] ${
                status?.model === m.id ? "bg-[#242736] border-l-2 border-[#a78bfa]" : "opacity-50"
              }`}
            >
              <div className="flex flex-col">
                <span className="text-[13px] font-semibold text-[#e5e0ed]">{m.label}</span>
                <span className="text-[10px] font-mono text-[#c9c4d7]">{m.note}</span>
              </div>
              <span className="bg-[#1a1d27] px-1.5 py-0.5 rounded text-[10px] font-mono text-[#a78bfa]">
                {m.context_k}K ctx
              </span>
            </div>
          ))}
        </div>
        <p className="text-[10px] font-mono text-[#474554] px-2">
          Active model set via{" "}
          <span className="text-[#94a3b8]">CEREBRO_CLAUDE_MODEL</span> env var
        </p>

        {/* Embedding notice — always shown */}
        <div className="flex items-center gap-2 px-2 py-1 bg-[#0e0d15] border border-[#242736] rounded">
          <span className="text-[11px] text-[#8b8fa8] font-mono">
            Embedding: nomic-embed-text (local, always)
          </span>
        </div>
      </section>
    );
  }

  const handleSelect = (name: string) => {
    void patch({ model: name });
  };

  const installedNames = new Set(models.map((m) => m.name));
  const recommended = RECOMMENDED.filter((r) => !installedNames.has(r.name));
  const mlxModels = models.filter((m) => m.provider === "mlx");

  return (
    <section className="space-y-4">
      {/* llama.cpp models */}
      <div>
        <p className="text-[10px] font-mono uppercase tracking-widest text-[#928ea0] mb-1 px-1">
          Local · llama.cpp
        </p>
        {llamaCppLoading ? (
          <p className="text-[11px] font-mono text-[#474554] px-2 py-1">Loading…</p>
        ) : llamaCppModels.length === 0 ? (
          <p className="text-[11px] font-mono text-[#474554] px-2 py-1">
            No GGUF models found
          </p>
        ) : (
          <div className="space-y-1">
            {llamaCppModels.map((m) => (
              <RadioRow
                key={m.name}
                name={m.name.replace(/\.GGUF$/i, "")}
                sub={`llama.cpp · ${m.size_gb > 0 ? `${m.size_gb} GB` : "GGUF"}`}
                badge="GGUF"
                isActive={m.name === activeModel}
                onClick={() => handleSelect(m.name)}
              />
            ))}
          </div>
        )}
      </div>

      {/* MLX models */}
      {mlxModels.length > 0 && (
        <div>
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#928ea0] mb-1 px-1">
            Apple Silicon · MLX
          </p>
          <div className="space-y-1">
            {mlxModels.map((m) => (
              <RadioRow
                key={m.name}
                name={m.name.split("/").pop() ?? m.name}
                sub="MLX · Apple Silicon"
                badge="MLX"
                isActive={m.name === activeModel}
                onClick={() => handleSelect(m.name)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Recommended models */}
      {recommended.length > 0 && (
        <div>
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#928ea0] mb-1 px-1">
            Recommended
          </p>
          <div className="space-y-1 opacity-60">
            {recommended.map((r) => (
              <RadioRow
                key={r.name}
                name={r.name}
                sub={`${r.note} · not pulled`}
                badge={r.ramGb}
                isActive={false}
                onClick={() => {}}
              />
            ))}
          </div>
          <p className="text-[10px] font-mono text-[#474554] px-2 mt-1">
            Place the GGUF file in <span className="text-[#94a3b8]">bin/models/</span> to install
          </p>
        </div>
      )}

      {/* Embedding notice */}
      <div className="flex items-center gap-2 px-2 py-1 bg-[#0e0d15] border border-[#242736] rounded">
        <svg className="w-3.5 h-3.5 text-[#928ea0]" viewBox="0 0 24 24" fill="currentColor">
          <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z" />
        </svg>
        <span className="text-[11px] text-[#8b8fa8] font-mono">
          Embedding: nomic-embed-text (fixed)
        </span>
      </div>
    </section>
  );
}
