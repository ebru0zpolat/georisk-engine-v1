import type { Severity } from "./severity";
import { severityColor } from "./severity";

type SnapshotHeaderProps = {
  assetName: string;
  sector: string;
  latitude: number;
  longitude: number;
  generatedAt: string;
  severity: Severity;
};

export default function SnapshotHeader({
  assetName,
  sector,
  latitude,
  longitude,
  generatedAt,
  severity,
}: SnapshotHeaderProps) {
  const generatedDate = new Date(generatedAt).toLocaleString();

  return (
    <header className="snapshot-header">
      <div className="snapshot-header-main">
        <h1>{assetName}</h1>
        <p className="snapshot-header-meta">
          <span className="snapshot-header-sector">{sector}</span>
          <span>·</span>
          <span>
            {latitude.toFixed(3)}, {longitude.toFixed(3)}
          </span>
        </p>
        <p className="snapshot-header-generated">Generated {generatedDate}</p>
      </div>
      <span
        className="snapshot-badge"
        style={{ backgroundColor: severityColor[severity] }}
        data-severity={severity}
      >
        {severity}
      </span>
    </header>
  );
}
