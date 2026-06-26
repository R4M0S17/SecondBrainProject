import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

export interface Command {
  name: string;
  description: string;
}

export const COMMAND_DEFS: { name: string; descriptionKey: string }[] = [
  { name: "/help", descriptionKey: "commands.help" },
  { name: "/clear", descriptionKey: "commands.clear" },
  { name: "/model", descriptionKey: "commands.model" },
  { name: "/status", descriptionKey: "commands.status" },
  { name: "/agents", descriptionKey: "commands.agents" },
  { name: "/index", descriptionKey: "commands.index" },
  { name: "/memory", descriptionKey: "commands.memory" },
  { name: "/export", descriptionKey: "commands.export" },
  { name: "/refresh", descriptionKey: "commands.refresh" },
  { name: "/settings", descriptionKey: "commands.settings" },
];

export function buildCommands(t: (key: string) => string): Command[] {
  return COMMAND_DEFS.map((d) => ({
    name: d.name,
    description: t(d.descriptionKey),
  }));
}

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
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const filter = query.toLowerCase();
  const COMMANDS = buildCommands(t);
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
