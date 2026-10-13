const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8002/v1";

export type DemoAsset = {
  id: string;
  name: string;
  sector: string;
  latitude: number;
  longitude: number;
  radius_km: number;
};

export type Insight = {
  category: string;
  severity: string;
  message: string;
};

export async function fetchDemoAssets(): Promise<DemoAsset[]> {
  const res = await fetch(`${API_BASE}/demo/assets`);
  if (!res.ok) throw new Error("Failed to fetch demo assets");
  return res.json();
}

export async function runDemo(assetId: string) {
  const res = await fetch(`${API_BASE}/demo/run?asset_id=${assetId}`);
  if (!res.ok) throw new Error("Failed to run demo");
  return res.json();
}

export function pdfUrl(assetId: string): string {
  return `${API_BASE}/demo/run/pdf?asset_id=${assetId}`;
}

export type CaseEvent = {
  timestamp: string;
  status: string;
  trigger_type: string;
  description: string;
};

export type Case = {
  id: string;
  asset_id: string;
  title: string;
  status: string;
  severity: string;
  trigger_type: string;
  created_at: string;
  updated_at: string;
  events: CaseEvent[];
};

export type CaseListResponse = {
  asset_id: string;
  open_count: number;
  cases: Case[];
};

export async function fetchCases(assetId: string): Promise<CaseListResponse> {
  const res = await fetch(`${API_BASE}/cases?asset_id=${assetId}`);
  if (!res.ok) throw new Error("Failed to fetch cases");
  return res.json();
}

export type PortfolioAsset = {
  asset_id: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  asset_value: number;
  building_type: string;
  use_class: string;
  construction_year?: number | null;
  floors?: number | null;
  insurance_coverage?: number | null;
  existing_adaptation_measures?: string[];
  ltv?: number | null;
  loan_id?: string | null;
  adaptation?: Record<string, unknown> | null;
};

export type PortfolioUploadResponse = {
  portfolio_id: string;
  valuation_date: string;
  asset_count: number;
  assets: PortfolioAsset[];
  source: string;
};

export type PortfolioDemoAssetRow = {
  asset_id: string;
  building_type: string;
  use_class: string;
  asset_value: number;
  hazard_composite: number;
  eal_absolute: number;
  eal_2030?: number | null;
  eal_2050?: number | null;
  recommended_measure_id?: string | null;
  avoided_loss: number;
  residual_eal: number;
  eal_audit_record_id?: string | null;
  methodology_version?: string | null;
  damage_curves_version?: string | null;
  calibration_badge?: string;
};

export type MethodologyStamp = {
  document: string;
  document_path: string;
  expected_loss: string;
  damage_curves: string;
  adaptation_evidence: string;
  pipeline: string;
  calibration_badge: string;
};

export type VerificationHazardStep = {
  hazard_id: string;
  intensity: number;
  curve_id: string;
  mdr: number;
  attribution_share: number;
  loss: number;
  formula: string;
};

export type VerificationWalkthrough = {
  asset_id: string;
  valuation_date: string;
  asset_value: number;
  building_type: string;
  use_class: string;
  trail_record_id: string;
  trail_record_hash: string;
  methodology_version: string;
  damage_curves_version: string;
  calibration_badge: string;
  vulnerability: number;
  combined_mdr: number;
  steps: VerificationHazardStep[];
  pipeline_eal: number;
  independent_eal: number;
  eal_2030_independent?: number | null;
  eal_2050_independent?: number | null;
  agreement: string;
  sample_report_path: string;
  sample_report_url: string;
};

export type ExcludedAssetRow = {
  asset_id: string;
  reason: string;
};

export type CoverageSummary = {
  submitted_count: number;
  analyzed_count: number;
  excluded_count: number;
  message: string;
  eal_scope: string;
  reason_counts: Record<string, number>;
  excluded: ExcludedAssetRow[];
};

export type PortfolioDemoNarrative = {
  portfolio_id: string;
  valuation_date: string;
  asset_count: number;
  source: string;
  currency?: string;
  methodology: MethodologyStamp;
  calibration_badge: string;
  coverage: CoverageSummary;
  upload: Record<string, unknown>;
  hazard: Record<string, unknown>;
  expected_loss: Record<string, unknown>;
  adaptation: Record<string, unknown>;
  avoided_loss: Record<string, unknown>;
  verification?: VerificationWalkthrough | null;
  assets: PortfolioDemoAssetRow[];
  honesty_note?: string | null;
};

export type PortfolioDemoRunResponse = {
  narrative: PortfolioDemoNarrative;
};

async function readApiError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const message = body?.error?.message || res.statusText;
    const coverageMsg = body?.error?.details?.coverage?.message;
    if (coverageMsg && !String(message).includes(coverageMsg)) {
      return `${message} (${coverageMsg})`;
    }
    return message;
  } catch {
    return res.statusText;
  }
}

export async function uploadPortfolioFile(
  file: File,
  valuationDate: string,
  portfolioId?: string,
): Promise<PortfolioUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("valuation_date", valuationDate);
  if (portfolioId) form.append("portfolio_id", portfolioId);
  const res = await fetch(`${API_BASE}/portfolio/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await readApiError(res));
  return res.json();
}

export async function runPortfolioDemo(body: {
  valuation_date: string;
  assets: PortfolioAsset[];
  portfolio_id?: string;
  max_assets?: number;
}): Promise<PortfolioDemoRunResponse> {
  const res = await fetch(`${API_BASE}/portfolio/demo-run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readApiError(res));
  return res.json();
}

export async function runGoldenAntalyaDemo(
  maxAssets = 100,
): Promise<PortfolioDemoRunResponse> {
  const res = await fetch(
    `${API_BASE}/portfolio/demo-run/golden-antalya?max_assets=${maxAssets}`,
    { method: "POST" },
  );
  if (!res.ok) throw new Error(await readApiError(res));
  return res.json();
}

export async function runGoldenRotterdamPortDemo(
  maxAssets = 100,
): Promise<PortfolioDemoRunResponse> {
  const res = await fetch(
    `${API_BASE}/portfolio/demo-run/golden-rotterdam-port?max_assets=${maxAssets}`,
    { method: "POST" },
  );
  if (!res.ok) throw new Error(await readApiError(res));
  return res.json();
}
