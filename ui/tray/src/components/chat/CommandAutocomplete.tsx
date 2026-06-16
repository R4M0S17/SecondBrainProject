import { useEffect, useRef } from "react";

export interface Command {
  name: string;
  description: string;
}

export const COMMANDS: Command[] = [
  { name: "/help", description: "Show available commands" },
  { name: "/clear", description: "Clear conversation history" },
  { name: "/model", description: "Show current active model" },
  { name: "/status", description: "Show system status (RAM, latency, model)" },
  { name: "/agents", description: "List available agents" },
  { name: "/index", description: "Re-index all watched folders" },
  { name: "/memory", description: "Show memory usage and recall stats" },
  { name: "/export", description: "Export conversation to file" },
  { name: "/refresh", description: "Refresh system status" },
  { name: "/settings", description: "Show current configuration" },
];

interface CommandAutocompleteProps {
  query: string;
  selectedIndex: number;
  onSelect: (cmd: string) => void;
}

export default function CommandAutocomplete({
  query,
  selectedIndex,
  onSelect,
}: CommandAutocompleteProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const filter = query.toLowerCase();
  const matches = COMMANDS.filter((c) => c.name.startsWith(filter));

  useEffect(() => {
    if (!containerRef.current || selectedIndex < 0) return;
    const item = containerRef.current.children[selectedIndex] as HTMLElement | undefined;
    item?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  if (matches.length === 0) return null;

  return (
    <div
      ref={containerRef}
      className="absolute bottom-full left-0 right-0 mb-1 bg-surface-container-low border border-outline-variant rounded-lg shadow-lg overflow-y-auto max-h-[240px] z-20"
      role="listbox"
    >
      {matches.map((cmd, i) => (
        <button
          key={cmd.name}
          role="option"
          aria-selected={i === selectedIndex}
          onClick={() => onSelect(cmd.name)}
          className={`w-full flex items-center gap-3 px-3 py-2 text-left transition-colors ${
            i === selectedIndex
              ? "bg-primary-container/20 text-primary-container"
              : "hover:bg-surface-container text-on-surface"
          }`}
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
