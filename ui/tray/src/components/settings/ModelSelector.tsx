import { useSettingsStore } from "../../stores/settings";
import { useSystemStore, selectIsClaudeMode } from "../../stores/system";
import { CLAUDE_MODELS } from "../../api/types";

const RECOMMENDED: { name: string; ramGb: string; note: string }[] = [
  { name: "Qwen3.5-2B-UD-Q4_K_XL.gguf", ramGb: "1.2 GB", note: "Multimodal · 262K ctx · fast" },
  { name: "Qwen_Qwen3.5-2B-Q4_K_M.gguf", ramGb: "1.3 GB", note: "Text-only · 262K ctx" },
  { name: "Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf", ramGb: "0.9 GB", note: "Code-specialized" },
  { name: "Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf", ramGb: "2.3 GB", note: "Strong reasoning" },
  { name: "Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf", ramGb: "1.8 GB", note: "Larger code model" },
  { name: "llama-3.2-3b-instruct-q4_k_m.gguf", ramGb: "1.9 GB", note: "Meta · efficient" },
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
        isActive ? "bg-surface-container border-l-2 border-primary-container" : "hover:bg-surface-container"
      }`}
    >
      <div className="flex items-center gap-2">
        <div
          className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center ${
            isActive ? "border-primary-container" : "border-outline"
          }`}
        >
          {isActive && <div className="w-1.5 h-1.5 bg-primary-container rounded-full" />}
        </div>
        <div className="flex flex-col">
          <span className="text-[13px] font-semibold leading-none mb-0.5 text-on-surface">
            {name}
          </span>
          <span className="text-[10px] font-mono text-on-surface-variant">{sub}</span>
        </div>
      </div>
      {badge && (
        <span className="bg-surface-container px-1.5 py-0.5 rounded text-[10px] font-mono text-on-surface-variant">
          {badge}
        </span>
      )}
    </div>
  );
}

export default function ModelSelector() {
  const { models, activeModel, llamaCppModels, llamaCppLoading, switchingModel, patch } = useSettingsStore();
  const status = useSystemStore((s) => s.status);
  const isCloud = selectIsClaudeMode(status);

  if (isCloud) {
    return (
      <section className="space-y-4">
        <p className="text-[10px] font-mono uppercase tracking-widest text-outline mb-1 px-1">
          Cloud · Claude API
        </p>
        <p className="text-[11px] text-on-surface-variant px-1 mb-2">
          Claude API — model managed by env var
        </p>
        <div className="space-y-1">
          {CLAUDE_MODELS.map((m) => (
            <div
              key={m.id}
              className={`flex items-center justify-between p-2 rounded-[6px] ${
                status?.model === m.id ? "bg-surface-container border-l-2 border-[#a78bfa]" : "opacity-50"
              }`}
            >
              <div className="flex flex-col">
                <span className="text-[13px] font-semibold text-on-surface">{m.label}</span>
                <span className="text-[10px] font-mono text-on-surface-variant">{m.note}</span>
              </div>
              <span className="bg-surface-container px-1.5 py-0.5 rounded text-[10px] font-mono text-[#a78bfa]">
                {m.context_k}K ctx
              </span>
            </div>
          ))}
        </div>
        <p className="text-[10px] font-mono text-outline px-2">
          Active model set via{" "}
          <span className="text-primary-container">CEREBRO_CLAUDE_MODEL</span> env var
        </p>

        {/* Embedding notice — always shown */}
        <div className="flex items-center gap-2 px-2 py-1 bg-surface-container-lowest border border-outline-variant rounded">
          <span className="text-[11px] text-outline font-mono">
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
        <p className="text-[10px] font-mono uppercase tracking-widest text-outline mb-1 px-1">
          Local · llama.cpp
        </p>
        {llamaCppLoading ? (
          <p className="text-[11px] font-mono text-outline px-2 py-1">Loading…</p>
        ) : llamaCppModels.length === 0 ? (
          <p className="text-[11px] font-mono text-outline px-2 py-1">
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

      {/* Switching indicator */}
      {switchingModel && (
        <div className="flex items-center gap-2 px-2 py-2 bg-surface-container border border-outline-variant rounded">
          <svg className="animate-spin h-3.5 w-3.5 text-primary-container" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-[11px] text-on-surface-variant font-mono">
            Switching model — restarting llama-server…
          </span>
        </div>
      )}

      {/* MLX models */}
      {mlxModels.length > 0 && (
        <div>
          <p className="text-[10px] font-mono uppercase tracking-widest text-outline mb-1 px-1">
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
          <p className="text-[10px] font-mono uppercase tracking-widest text-outline mb-1 px-1">
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
          <p className="text-[10px] font-mono text-outline px-2 mt-1">
            Place the GGUF file in <span className="text-primary-container">bin/models/</span> to install
          </p>
        </div>
      )}

      {/* Embedding notice */}
      <div className="flex items-center gap-2 px-2 py-1 bg-surface-container-lowest border border-outline-variant rounded">
        <svg className="w-3.5 h-3.5 text-outline" viewBox="0 0 24 24" fill="currentColor">
          <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z" />
        </svg>
        <span className="text-[11px] text-outline font-mono">
          Embedding: nomic-embed-text (fixed)
        </span>
      </div>
    </section>
  );
}
