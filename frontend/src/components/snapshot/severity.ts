export type Severity = "CRITICAL" | "ELEVATED" | "NORMAL";

export function severityFromScores(zScore: number, compositeScore: number): Severity {
  const absZ = Math.abs(zScore);
  if (absZ >= 3.0 || compositeScore >= 70) return "CRITICAL";
  if (absZ >= 2.0 || compositeScore >= 40) return "ELEVATED";
  return "NORMAL";
}

export function compositeScore(zScore: number, coastalExposureScore: number): number {
  const value = ((zScore / 5) * 0.6 + coastalExposureScore * 0.4) * 100;
  return Math.max(0, Math.min(100, Math.round(value)));
}

export const severityColor: Record<Severity, string> = {
  CRITICAL: "#dc2626",
  ELEVATED: "#d97706",
  NORMAL: "#16a34a",
};
