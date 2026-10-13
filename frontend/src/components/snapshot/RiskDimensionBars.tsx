import { severityColor } from "./severity";

type RiskDimensionBarsProps = {
  emissionZScore: number;
  seaLevelTrendMmPerYear: number;
  coastalExposureScore: number;
  ipccProjectedRiseM: number;
  regulatoryExposure: "Low" | "Moderate" | "High";
};

function barColorFor(ratio: number): string {
  if (ratio >= 0.66) return severityColor.CRITICAL;
  if (ratio >= 0.33) return severityColor.ELEVATED;
  return severityColor.NORMAL;
}

const REGULATORY_RATIO: Record<RiskDimensionBarsProps["regulatoryExposure"], number> = {
  Low: 0.2,
  Moderate: 0.55,
  High: 0.9,
};

export default function RiskDimensionBars({
  emissionZScore,
  seaLevelTrendMmPerYear,
  coastalExposureScore,
  ipccProjectedRiseM,
  regulatoryExposure,
}: RiskDimensionBarsProps) {
  const dimensions = [
    {
      label: "NO₂ emission anomaly (Z-score)",
      value: emissionZScore.toFixed(2),
      ratio: Math.min(1, Math.abs(emissionZScore) / 5),
    },
    {
      label: "Sea level rise rate (mm/yr)",
      value: seaLevelTrendMmPerYear.toFixed(2),
      ratio: Math.min(1, Math.abs(seaLevelTrendMmPerYear) / 10),
    },
    {
      label: "Coastal proximity (exposure score)",
      value: coastalExposureScore.toFixed(2),
      ratio: Math.min(1, Math.max(0, coastalExposureScore)),
    },
    {
      label: "IPCC SSP2-4.5 projected rise (m)",
      value: ipccProjectedRiseM.toFixed(2),
      ratio: Math.min(1, Math.abs(ipccProjectedRiseM) / 1.0),
    },
    {
      label: "Regulatory exposure",
      value: regulatoryExposure,
      ratio: REGULATORY_RATIO[regulatoryExposure],
    },
  ];

  return (
    <section className="snapshot-dimensions" aria-label="Risk dimensions">
      <h2>Risk dimensions</h2>
      <div className="snapshot-dimension-list">
        {dimensions.map((dimension) => (
          <div className="snapshot-dimension-row" key={dimension.label}>
            <span className="snapshot-dimension-label">{dimension.label}</span>
            <div className="snapshot-dimension-track">
              <div
                className="snapshot-dimension-fill"
                style={{
                  width: `${dimension.ratio * 100}%`,
                  backgroundColor: barColorFor(dimension.ratio),
                }}
              />
            </div>
            <span className="snapshot-dimension-value">{dimension.value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
