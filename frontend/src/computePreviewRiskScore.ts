const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.PROD
    ? // The public demo host published in the docs section of the landing page.
      "https://api-production-5880.up.railway.app/v1"
    : "http://localhost:8002/v1");

export type ScorecardComponent = {
  id: string;
  label: string;
  score: number;
};

export type ResolvedLocation = {
  latitude: number;
  longitude: number;
  radius_km: number;
  asset_name: string;
  sector: string;
  resolution_method: string;
  resolution_detail?: string | null;
};

export type PreviewRiskScorecard = {
  indicative_climate_risk_score: number;
  risk_band: string;
  headline: string;
  location_input: string;
  resolved: ResolvedLocation;
  components: ScorecardComponent[];
  top_flags: string[];
  interpretation: string;
  disclaimer: string;
  audit_id: string;
  generated_at: string;
  deep_dive_endpoints: Record<string, string>;
};

export type PreviewRiskScoreInput = {
  location: string;
  asset_name?: string;
  radius_km?: number;
  sector?: string;
};

/**
 * UC-01: 1-minute indicative climate risk scorecard from coordinate, address, or demo id.
 */
export async function computePreviewRiskScore(
  input: PreviewRiskScoreInput,
): Promise<PreviewRiskScorecard> {
  const res = await fetch(`${API_BASE}/risk/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      location: input.location,
      asset_name: input.asset_name,
      radius_km: input.radius_km ?? 10,
      sector: input.sector ?? "industrial",
    }),
  });

  if (!res.ok) {
    let message = `Preview score failed (${res.status})`;
    try {
      const err = (await res.json()) as { error?: { message?: string } };
      if (err.error?.message) message = err.error.message;
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }

  return res.json() as Promise<PreviewRiskScorecard>;
}
