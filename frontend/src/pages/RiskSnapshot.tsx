import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { fetchCases, runDemo, type Case } from "../api";
import SnapshotHeader from "../components/snapshot/SnapshotHeader";
import MetricCardGrid from "../components/snapshot/MetricCardGrid";
import RiskDimensionBars from "../components/snapshot/RiskDimensionBars";
import SignalList from "../components/snapshot/SignalList";
import CaseTimeline from "../components/snapshot/CaseTimeline";
import AnalystVerdict from "../components/snapshot/AnalystVerdict";
import SnapshotFooter from "../components/snapshot/SnapshotFooter";
import { compositeScore, severityFromScores } from "../components/snapshot/severity";
import "./RiskSnapshot.css";

type DemoResult = {
  demo_id: string;
  asset: {
    name: string;
    sector: string;
    latitude: number;
    longitude: number;
    radius_km: number;
  };
  flags: string[];
  features: {
    oras5: {
      sea_level_trend_mm_per_year: number;
    };
  };
  audit: { generated_at: string };
  emission_zscore: number;
  anomaly_flag: boolean;
  coastal_exposure_score: number;
};

const ANOMALY_THRESHOLD = 2.0;
const IPCC_PROJECTION_YEARS = 30;

function regulatoryExposureFor(flags: string[], anomalyFlag: boolean): "Low" | "Moderate" | "High" {
  if (anomalyFlag && flags.includes("elevated_pollution")) return "High";
  if (flags.length > 0) return "Moderate";
  return "Low";
}

export default function RiskSnapshot() {
  const { assetId } = useParams<{ assetId: string }>();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [result, setResult] = useState<DemoResult | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!assetId) return;

    Promise.all([runDemo(assetId), fetchCases(assetId)])
      .then(([demoData, caseData]) => {
        setResult(demoData as DemoResult);
        setCases(caseData.cases);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load snapshot");
      });
  }, [assetId]);

  if (error) {
    return (
      <main className="snapshot-page snapshot-state">
        <p className="status error">{error}</p>
      </main>
    );
  }

  if (!result) {
    return (
      <main className="snapshot-page snapshot-state">
        <p className="status">Loading risk snapshot...</p>
      </main>
    );
  }

  const seaLevelTrend = result.features.oras5.sea_level_trend_mm_per_year;
  const ipccProjectedRiseM = (seaLevelTrend * IPCC_PROJECTION_YEARS) / 1000;
  const composite = compositeScore(result.emission_zscore, result.coastal_exposure_score);
  const severity = severityFromScores(result.emission_zscore, composite);
  const openCasesCount = cases.filter((c) => c.status === "open").length;
  const regulatoryExposure = regulatoryExposureFor(result.flags, result.anomaly_flag);
  const shareToken = token || result.demo_id;

  return (
    <main className="snapshot-page">
      <SnapshotHeader
        assetName={result.asset.name}
        sector={result.asset.sector}
        latitude={result.asset.latitude}
        longitude={result.asset.longitude}
        generatedAt={result.audit.generated_at}
        severity={severity}
      />

      <MetricCardGrid
        emissionZScore={result.emission_zscore}
        anomalyThreshold={ANOMALY_THRESHOLD}
        coastalExposureScore={result.coastal_exposure_score}
        openCasesCount={openCasesCount}
        compositeScore={composite}
      />

      <RiskDimensionBars
        emissionZScore={result.emission_zscore}
        seaLevelTrendMmPerYear={seaLevelTrend}
        coastalExposureScore={result.coastal_exposure_score}
        ipccProjectedRiseM={ipccProjectedRiseM}
        regulatoryExposure={regulatoryExposure}
      />

      <div className="snapshot-columns">
        <SignalList
          anomalyFlag={result.anomaly_flag}
          emissionZScore={result.emission_zscore}
          coastalExposureScore={result.coastal_exposure_score}
          seaLevelTrendMmPerYear={seaLevelTrend}
          ipccProjectedRiseM={ipccProjectedRiseM}
          flags={result.flags}
          severity={severity}
        />
        <CaseTimeline cases={cases} />
      </div>

      <AnalystVerdict
        severity={severity}
        compositeScore={composite}
        openCasesCount={openCasesCount}
        flags={result.flags}
      />

      <SnapshotFooter assetId={assetId ?? ""} shareToken={shareToken} />
    </main>
  );
}
