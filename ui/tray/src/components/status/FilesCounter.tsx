import { useSettingsStore } from "../../stores/settings";

interface FilesCounterProps {
  count: number;
}

export default function FilesCounter({ count }: FilesCounterProps) {
  const folders = useSettingsStore((s) => s.config?.watched_folders ?? []);
  const startIndexing = useSettingsStore((s) => s.startIndexing);

  const handleClick = () => {
    void startIndexing(folders);
  };

  return (
    <button
      onClick={handleClick}
      className="underline decoration-[#242736] underline-offset-2 hover:text-[#e5e0ed] transition-colors cursor-pointer"
      title="Click to re-index"
    >
      {count} files
    </button>
  );
}
