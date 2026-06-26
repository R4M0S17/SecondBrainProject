import { useTranslation } from "react-i18next";
import type { WorkflowParameter } from "../../api/types";

interface WorkflowParamFormProps {
  parameters: WorkflowParameter[];
  values: Record<string, string>;
  onChange: (name: string, value: string) => void;
}

export default function WorkflowParamForm({
  parameters,
  values,
  onChange,
}: WorkflowParamFormProps) {
  const { t } = useTranslation();

  if (parameters.length === 0) return null;

  return (
    <section>
      <h3 className="text-label-caps text-outline tracking-wider uppercase mb-3">
        {t("workflows.parameters")}
      </h3>
      <div className="space-y-3">
        {parameters.map((p) => (
          <label key={p.name} className="block">
            <span className="text-[12px] text-on-surface-variant mb-1 block">
              {p.description || p.name}
              <span className="text-outline ml-1">({p.type})</span>
            </span>
            <div className="input-glow rounded-xl border border-outline-variant/30 bg-surface-container-low/40 px-3 py-2">
              <input
                type={p.type === "number" ? "number" : "text"}
                value={values[p.name] ?? p.default ?? ""}
                onChange={(e) => onChange(p.name, e.target.value)}
                className="w-full bg-transparent text-[13px] text-on-surface outline-none"
                placeholder={p.default}
              />
            </div>
          </label>
        ))}
      </div>
    </section>
  );
}
