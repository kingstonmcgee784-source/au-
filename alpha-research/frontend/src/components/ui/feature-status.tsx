import { Construction } from "lucide-react";

interface FeatureStatusProps {
  title?: string;
  summary: string;
  planned: string[];
  dependsOn?: string[];
}

/** Clearly marks a section that is not built yet and says what it will do. */
export function FeatureStatus({
  title = "Not built yet",
  summary,
  planned,
  dependsOn,
}: FeatureStatusProps) {
  return (
    <section className="rounded-lg border border-dashed border-warning/40 bg-warning-soft/40 p-5">
      <div className="flex items-start gap-3">
        <Construction className="mt-0.5 size-5 shrink-0 text-warning" aria-hidden />
        <div className="space-y-3 text-sm">
          <div>
            <h2 className="font-semibold text-warning">{title}</h2>
            <p className="mt-1 text-ink-muted">{summary}</p>
          </div>
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-faint">
              Planned capabilities
            </h3>
            <ul className="mt-1.5 list-disc space-y-1 pl-5 text-ink-muted">
              {planned.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          {dependsOn && dependsOn.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-faint">
                Depends on
              </h3>
              <ul className="mt-1.5 list-disc space-y-1 pl-5 text-ink-muted">
                {dependsOn.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
