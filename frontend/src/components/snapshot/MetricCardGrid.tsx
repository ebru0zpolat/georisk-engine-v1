type MetricCardGridProps = {
  emissionZScore: number;
  anomalyThreshold: number;
  coastalExposureScore: number;
  openCasesCount: number;
  compositeScore: number;
};

type Metric = {
  label: string;
  value: string;
  note: string;
};

export default function MetricCardGrid({
  emissionZScore,
  anomalyThreshold,
  coastalExposureScore,
  openCasesCount,
  compositeScore,
}: MetricCardGridProps) {
  const metrics: Metric[] = [
    {
      label: "Emission Z-score",
      value: emissionZScore.toFixed(2),
      note: `Anomaly threshold ±${anomalyThreshold.toFixed(1)}`,
    },
    {
      label: "Sea level exposure",
      value: coastalExposureScore.toFixed(2),
      note: "0 (low) – 1 (high)",
    },
    {
      label: "Open cases",
      value: String(openCasesCount),
      note: openCasesCount === 1 ? "case requires attention" : "cases require attention",
    },
    {
      label: "Composite risk score",
      value: String(compositeScore),
      note: "0-100 scale",
    },
  ];

  return (
    <section className="snapshot-metric-grid" aria-label="Key risk metrics">
      {metrics.map((metric) => (
        <article className="snapshot-metric-card" key={metric.label}>
          <span className="snapshot-metric-label">{metric.label}</span>
          <strong className="snapshot-metric-value">{metric.value}</strong>
          <span className="snapshot-metric-note">{metric.note}</span>
        </article>
      ))}
    </section>
  );
}
