interface Command {
  name: string;
  description: string;
}

const COMMANDS: Command[] = [
  { name: "/index", description: "Re-index all watched folders" },
  { name: "/clear", description: "Clear conversation history" },
  { name: "/model", description: "Switch the active model" },
  { name: "/status", description: "Show system status" },
  { name: "/help", description: "Show available commands" },
];

interface CommandAutocompleteProps {
  query: string;
  onSelect: (cmd: string) => void;
}

export default function CommandAutocomplete({
  query,
  onSelect,
}: CommandAutocompleteProps) {
  const filter = query.toLowerCase();
  const matches = COMMANDS.filter((c) => c.name.startsWith(filter));

  if (matches.length === 0) return null;

  return (
    <div className="absolute bottom-full left-0 right-0 mb-1 bg-surface-container-low border border-outline-variant rounded shadow-lg overflow-hidden z-20">
      {matches.map((cmd) => (
        <button
          key={cmd.name}
          onClick={() => onSelect(cmd.name)}
          className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-surface-container transition-colors"
        >
          <span className="font-mono text-[13px] text-primary-container shrink-0">
            {cmd.name}
          </span>
          <span className="text-[12px] text-outline truncate">
            {cmd.description}
          </span>
        </button>
      ))}
    </div>
  );
}
