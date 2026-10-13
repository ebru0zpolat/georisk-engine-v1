import type { Severity } from "./severity";
import { severityColor } from "./severity";

type AnalystVerdictProps = {
  severity: Severity;
  compositeScore: number;
  openCasesCount: number;
  flags: string[];
};

export default function AnalystVerdict({
  severity,
  compositeScore,
  openCasesCount,
  flags,
}: AnalystVerdictProps) {
  let text: string;

  if (severity === "CRITICAL") {
    const riskList = flags.length ? flags.map((f) => f.replace(/_/g, " ")).join(", ") : "multiple risk factors";
    text = `This asset presents compounding risks (${riskList}) within a single reporting cycle, with a composite risk score of ${compositeScore}/100 and ${openCasesCount} open case${openCasesCount === 1 ? "" : "s"}. Immediate review is recommended.`;
  } else if (severity === "ELEVATED") {
    const riskType = flags[0]?.replace(/_/g, " ") ?? "emission and exposure signals";
    text = `This asset shows ${riskType} above baseline, with a composite risk score of ${compositeScore}/100 and ${openCasesCount} open case${openCasesCount === 1 ? "" : "s"}. Monitor closely and revisit at the next reporting cycle.`;
  } else {
    text = "Risk within acceptable parameters. No immediate action required.";
  }

  return (
    <section
      className="snapshot-verdict"
      style={{ borderLeftColor: severityColor[severity] }}
      aria-label="Analyst recommendation"
    >
      <h2>Analyst recommendation</h2>
      <p>{text}</p>
    </section>
  );
}
