import type { Severity } from "./severity";

type SignalListProps = {
  anomalyFlag: boolean;
  emissionZScore: number;
  coastalExposureScore: number;
  seaLevelTrendMmPerYear: number;
  ipccProjectedRiseM: number;
  flags: string[];
  severity: Severity;
};

export default function SignalList({
  anomalyFlag,
  emissionZScore,
  coastalExposureScore,
  seaLevelTrendMmPerYear,
  ipccProjectedRiseM,
  flags,
  severity,
}: SignalListProps) {
  const signals: string[] = [];

  signals.push(
    anomalyFlag
      ? `NO₂ emission anomaly detected — Z-score ${emissionZScore.toFixed(2)} exceeds threshold.`
      : `NO₂ emissions within normal range — Z-score ${emissionZScore.toFixed(2)}.`,
  );

  signals.push(
    `Sea level rise rate of ${seaLevelTrendMmPerYear.toFixed(2)} mm/yr projects to ${ipccProjectedRiseM.toFixed(2)} m under SSP2-4.5.`,
  );

  signals.push(
    coastalExposureScore >= 0.5
      ? `Coastal exposure score of ${coastalExposureScore.toFixed(2)} indicates elevated proximity risk.`
      : `Coastal exposure score of ${coastalExposureScore.toFixed(2)} indicates limited proximity risk.`,
  );

  for (const flag of flags) {
    signals.push(`Component flag: ${flag.replace(/_/g, " ")}.`);
  }

  signals.push(
    severity === "CRITICAL"
      ? "Composite risk places this asset in the highest portfolio risk tier."
      : severity === "ELEVATED"
        ? "Composite risk places this asset above baseline portfolio risk."
        : "Composite risk is within acceptable portfolio parameters.",
  );

  return (
    <section className="snapshot-signals" aria-label="Key signals">
      <h2>Key signals</h2>
      <ul>
        {signals.slice(0, 6).map((signal, index) => (
          <li key={index}>{signal}</li>
        ))}
      </ul>
    </section>
  );
}
