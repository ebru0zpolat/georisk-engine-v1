import type { Case } from "../../api";

type CaseTimelineProps = {
  cases: Case[];
};

type TimelineEntry = {
  key: string;
  timestamp: string;
  status: string;
  triggerType: string;
  description: string;
};

export default function CaseTimeline({ cases }: CaseTimelineProps) {
  const entries: TimelineEntry[] = cases
    .flatMap((c) =>
      c.events.map((event, index) => ({
        key: `${c.id}-${index}`,
        timestamp: event.timestamp,
        status: event.status,
        triggerType: event.trigger_type,
        description: event.description,
      })),
    )
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, 4);

  return (
    <section className="snapshot-timeline" aria-label="Case activity timeline">
      <h2>Case activity</h2>
      {entries.length === 0 ? (
        <p className="snapshot-timeline-empty">No case activity recorded.</p>
      ) : (
        <ol>
          {entries.map((entry) => (
            <li key={entry.key}>
              <span className="snapshot-timeline-date">
                {new Date(entry.timestamp).toLocaleDateString()}
              </span>
              <span className="snapshot-timeline-status">
                {entry.status.replace(/_/g, " ")}
                <span className="snapshot-timeline-trigger">{entry.triggerType}</span>
              </span>
              <p>{entry.description}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
