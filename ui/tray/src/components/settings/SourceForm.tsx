import type { SyncSourceType } from "../../api/types";
import { SOURCE_TYPES } from "./SourceList";

interface FormState {
  source_type: SyncSourceType;
  uri: string;
  label: string;
  interval_minutes: number;
  tags: string;
  schedule_cron: string;
}

interface SourceFormProps {
  form: FormState;
  formError: string | null;
  onChange: (form: FormState) => void;
  onSubmit: () => void;
  onCancel: () => void;
}

export default function SourceForm({ form, formError, onChange, onSubmit, onCancel }: SourceFormProps) {
  return (
    <div className="p-5 mb-5 rounded-[12px] bg-surface-container-low border border-outline-variant space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[14px] font-semibold text-on-surface">New Link</h3>
        <button
          onClick={onCancel}
          className="text-[12px] text-outline hover:text-on-surface transition-colors"
        >
          Cancel
        </button>
      </div>

      <div>
        <label className="block text-[10px] font-bold text-outline mb-1.5 uppercase tracking-wider">Type</label>
        <div className="flex gap-2">
          {SOURCE_TYPES.map((opt) => (
            <button
              key={opt.id}
              onClick={() => onChange({ ...form, source_type: opt.id })}
              className={`flex-1 py-2 rounded-[6px] text-[12px] font-semibold transition-colors ${
                form.source_type === opt.id
                  ? "bg-primary-container text-on-surface border border-primary-container"
                  : "bg-surface-container border border-outline-variant text-outline hover:border-outline"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <label className="block text-[10px] font-bold text-outline mb-1 uppercase tracking-wider">Label</label>
          <input
            type="text"
            value={form.label}
            onChange={(e) => onChange({ ...form, label: e.target.value })}
            placeholder="My Feed"
            className="w-full px-3 py-2 rounded-[6px] bg-surface-container border border-outline-variant text-[13px] text-on-surface placeholder:text-outline/40 focus:outline-none focus:border-primary-container"
          />
        </div>
        <div className="col-span-2">
          <label className="block text-[10px] font-bold text-outline mb-1 uppercase tracking-wider">URL *</label>
          <input
            type="url"
            value={form.uri}
            onChange={(e) => onChange({ ...form, uri: e.target.value })}
            placeholder={SOURCE_TYPES.find((t) => t.id === form.source_type)?.hint ?? "URL"}
            className="w-full px-3 py-2 rounded-[6px] bg-surface-container border border-outline-variant text-[13px] text-on-surface font-mono placeholder:text-outline/40 focus:outline-none focus:border-primary-container"
          />
        </div>
        <div>
          <label className="block text-[10px] font-bold text-outline mb-1 uppercase tracking-wider">Interval (min)</label>
          <input
            type="number"
            value={form.interval_minutes}
            onChange={(e) => onChange({ ...form, interval_minutes: Math.max(5, Number(e.target.value)) })}
            min={5}
            className="w-full px-3 py-2 rounded-[6px] bg-surface-container border border-outline-variant text-[13px] text-on-surface focus:outline-none focus:border-primary-container"
          />
        </div>
        <div>
          <label className="block text-[10px] font-bold text-outline mb-1 uppercase tracking-wider">Tags</label>
          <input
            type="text"
            value={form.tags}
            onChange={(e) => onChange({ ...form, tags: e.target.value })}
            placeholder="AI, news, tech"
            className="w-full px-3 py-2 rounded-[6px] bg-surface-container border border-outline-variant text-[13px] text-on-surface placeholder:text-outline/40 focus:outline-none focus:border-primary-container"
          />
        </div>
        <div className="col-span-2">
          <label className="block text-[10px] font-bold text-outline mb-1 uppercase tracking-wider">Schedule (cron)</label>
          <input
            type="text"
            value={form.schedule_cron}
            onChange={(e) => onChange({ ...form, schedule_cron: e.target.value })}
            placeholder="0 3 * * * (daily 3AM) — leave empty for interval-based"
            className="w-full px-3 py-2 rounded-[6px] bg-surface-container border border-outline-variant text-[13px] text-on-surface font-mono placeholder:text-outline/40 focus:outline-none focus:border-primary-container"
          />
        </div>
      </div>

      {formError && <div className="text-[12px] text-error">{formError}</div>}

      <button
        onClick={onSubmit}
        className="w-full py-2.5 rounded-[6px] text-[13px] font-semibold bg-primary-container text-on-surface hover:opacity-90 transition-opacity"
      >
        Add to List
      </button>
    </div>
  );
}
