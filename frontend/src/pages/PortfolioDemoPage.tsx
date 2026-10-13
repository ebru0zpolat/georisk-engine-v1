import { useRef, useState } from "react";
import {
  runGoldenAntalyaDemo,
  runGoldenRotterdamPortDemo,
  runPortfolioDemo,
  uploadPortfolioFile,
  type PortfolioDemoNarrative,
} from "../api";

const STEPS = [
  { id: "upload", label: "Upload" },
  { id: "hazard", label: "Hazard" },
  { id: "expected_loss", label: "Expected loss" },
  { id: "adaptation", label: "Adaptation" },
  { id: "avoided_loss", label: "Avoided loss" },
] as const;

function money(n: number | undefined | null, currency = "TRY"): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(n);
}

function pct(n: number | undefined): string {
  if (n === undefined || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

function MethodBadge({
  methodology,
  calibration,
}: {
  methodology?: string | null;
  calibration?: string | null;
}) {
  return (
    <span className="pdemo-badges">
      {methodology ? <span className="pdemo-badge method">{methodology}</span> : null}
      {calibration ? (
        <span className="pdemo-badge calib">{calibration}</span>
      ) : null}
    </span>
  );
}

function Metric({
  label,
  value,
  methodology,
  calibration,
}: {
  label: string;
  value: string;
  methodology?: string | null;
  calibration?: string | null;
}) {
  return (
    <div>
      <dt>
        {label}
        <MethodBadge methodology={methodology} calibration={calibration} />
      </dt>
      <dd>{value}</dd>
    </div>
  );
}

export default function PortfolioDemoPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [valuationDate, setValuationDate] = useState("2021-07-01");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [narrative, setNarrative] = useState<PortfolioDemoNarrative | null>(null);
  const [activeStep, setActiveStep] = useState<(typeof STEPS)[number]["id"]>("upload");

  async function withBusy(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo run failed");
      setNarrative(null);
    } finally {
      setBusy(false);
    }
  }

  async function onUploadAndRun() {
    await withBusy(async () => {
      const file = fileRef.current?.files?.[0];
      if (!file) throw new Error("Choose a CSV or GeoJSON portfolio file first.");
      setActiveStep("upload");
      const uploaded = await uploadPortfolioFile(file, valuationDate);
      setActiveStep("hazard");
      const result = await runPortfolioDemo({
        valuation_date: uploaded.valuation_date,
        portfolio_id: uploaded.portfolio_id,
        assets: uploaded.assets,
        max_assets: Math.min(uploaded.asset_count, 100),
      });
      setNarrative(result.narrative);
      setActiveStep("avoided_loss");
    });
  }

  async function onGoldenAntalyaRun() {
    await withBusy(async () => {
      setActiveStep("upload");
      setActiveStep("hazard");
      const result = await runGoldenAntalyaDemo(100);
      setNarrative(result.narrative);
      setValuationDate(result.narrative.valuation_date);
      setActiveStep("avoided_loss");
    });
  }

  async function onGoldenRotterdamRun() {
    await withBusy(async () => {
      setActiveStep("upload");
      setActiveStep("hazard");
      const result = await runGoldenRotterdamPortDemo(100);
      setNarrative(result.narrative);
      setValuationDate(result.narrative.valuation_date);
      setActiveStep("avoided_loss");
    });
  }

  const stepIndex = STEPS.findIndex((s) => s.id === activeStep);
  const calib =
    narrative?.calibration_badge ??
    narrative?.methodology?.calibration_badge ??
    "synthetic calibration v0.2";
  const meth = narrative?.methodology;
  const currency = narrative?.currency ?? "TRY";

  return (
    <main className="pdemo-shell">
      <header className="pdemo-header">
        <a className="pdemo-brand" href="/">
          GeoRisk Engine
        </a>
        <p className="pdemo-tagline">
          From climate maps to financeable adaptation: converting location-level climate
          hazards into asset exposure, financial loss and investment priorities.
        </p>
        <p className="pdemo-honesty">
          Demo numbers use the five-layer pipeline + expected-loss engine — never the
          SHA-256 <code>/v1/risk/score</code> stub.
          <MethodBadge
            methodology={meth?.document ?? meth?.expected_loss}
            calibration={calib}
          />
          {meth?.document_path ? (
            <a
              className="pdemo-method-link"
              href={`https://github.com/ebru0zpolat/georisk-engine/blob/main/${meth.document_path}`}
              target="_blank"
              rel="noreferrer"
            >
              Methodology note
            </a>
          ) : null}
        </p>
      </header>

      <ol className="pdemo-steps" aria-label="Demo narrative steps">
        {STEPS.map((step, i) => (
          <li
            key={step.id}
            className={
              i < stepIndex ? "done" : i === stepIndex ? "active" : narrative ? "done" : ""
            }
          >
            <span className="pdemo-step-num">{i + 1}</span>
            <span>{step.label}</span>
          </li>
        ))}
      </ol>

      <section className="pdemo-panel" aria-label="Portfolio upload">
        <h1>Portfolio demo</h1>
        <p className="pdemo-lead">
          One screen: upload a portfolio, then read hazard → expected loss → adaptation →
          avoided loss. No standalone map views. Phase A requires{" "}
          <strong>latitude/longitude</strong> on each asset — address geocoding is not
          supported yet (rows without coordinates are listed as excluded, never dropped
          silently).
        </p>

        <div className="pdemo-controls">
          <label className="pdemo-field">
            <span>Valuation date</span>
            <input
              type="date"
              value={valuationDate}
              onChange={(e) => setValuationDate(e.target.value)}
              disabled={busy}
            />
          </label>
          <label className="pdemo-field pdemo-file">
            <span>CSV or GeoJSON</span>
            <input ref={fileRef} type="file" accept=".csv,.geojson,.json" disabled={busy} />
          </label>
          <div className="pdemo-actions">
            <button type="button" className="pdemo-btn primary" disabled={busy} onClick={onUploadAndRun}>
              {busy ? "Running…" : "Upload & run"}
            </button>
            <button type="button" className="pdemo-btn" disabled={busy} onClick={onGoldenAntalyaRun}>
              Load Antalya golden (TRY)
            </button>
            <button type="button" className="pdemo-btn" disabled={busy} onClick={onGoldenRotterdamRun}>
              Load Rotterdam port golden (EUR)
            </button>
          </div>
        </div>

        {error ? <p className="pdemo-error" role="alert">{error}</p> : null}
      </section>

      {narrative ? (
        <section className="pdemo-narrative" aria-live="polite">
          <aside
            className={
              narrative.coverage.excluded_count > 0
                ? "pdemo-coverage warn"
                : "pdemo-coverage ok"
            }
            role="status"
            aria-label="Analysis coverage"
          >
            <strong>{narrative.coverage.message}</strong>
            <span>
              Portfolio EAL covers <em>{narrative.coverage.eal_scope}</em>.
            </span>
            {narrative.coverage.excluded_count > 0 ? (
              <details className="pdemo-excluded">
                <summary>
                  Excluded assets ({narrative.coverage.excluded_count})
                </summary>
                <ul>
                  {narrative.coverage.excluded.map((row) => (
                    <li key={`${row.asset_id}-${row.reason}`}>
                      <code>{row.asset_id}</code> — {row.reason}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </aside>

          {narrative.honesty_note ? (
            <aside className="pdemo-coverage ok" role="note">
              <strong>Geographic / calibration note</strong>
              <span>{narrative.honesty_note}</span>
              <span>
                Display currency: <code>{currency}</code>
              </span>
            </aside>
          ) : null}

          <article className="pdemo-block" data-step="upload">
            <h2>1. Upload</h2>
            <p>{String(narrative.upload.message ?? "")}</p>
            <dl className="pdemo-metrics">
              <Metric label="Portfolio" value={narrative.portfolio_id} calibration={calib} />
              <Metric
                label="Analyzed assets"
                value={`${narrative.coverage.analyzed_count} of ${narrative.coverage.submitted_count}`}
                methodology={String(narrative.upload.methodology_version ?? meth?.pipeline)}
                calibration={calib}
              />
              <Metric label="Valuation date" value={narrative.valuation_date} calibration={calib} />
              <Metric label="Source" value={narrative.source} calibration={calib} />
            </dl>
          </article>

          <article className="pdemo-block" data-step="hazard">
            <h2>2. Hazard</h2>
            <p>{String(narrative.hazard.message ?? "")}</p>
            <dl className="pdemo-metrics">
              <Metric
                label="Mean composite intensity"
                value={pct(Number(narrative.hazard.mean_composite_intensity))}
                methodology={String(narrative.hazard.methodology_version ?? "hazard-stub-v0.2")}
                calibration={calib}
              />
            </dl>
            <ul className="pdemo-bars">
              {Object.entries(
                (narrative.hazard.mean_components as Record<string, number>) ?? {},
              ).map(([name, value]) => (
                <li key={name}>
                  <span>{name.replace(/_/g, " ")}</span>
                  <div className="pdemo-bar-track">
                    <div className="pdemo-bar-fill" style={{ width: `${value * 100}%` }} />
                  </div>
                  <span>
                    {pct(value)}
                    <MethodBadge
                      methodology={String(narrative.hazard.methodology_version ?? "hazard-stub-v0.2")}
                      calibration={calib}
                    />
                  </span>
                </li>
              ))}
            </ul>
          </article>

          <article className="pdemo-block" data-step="expected_loss">
            <h2>3. Expected loss</h2>
            <p>{String(narrative.expected_loss.message ?? "")}</p>
            <dl className="pdemo-metrics">
              <Metric
                label="EAL (analyzed assets only)"
                value={money(Number(narrative.expected_loss.eal_sum), currency)}
                methodology={String(
                  narrative.expected_loss.methodology_version ?? meth?.expected_loss,
                )}
                calibration={calib}
              />
              <Metric
                label="EAL (mean / analyzed asset)"
                value={money(Number(narrative.expected_loss.eal_mean), currency)}
                methodology={String(
                  narrative.expected_loss.methodology_version ?? meth?.expected_loss,
                )}
                calibration={calib}
              />
              <Metric
                label="2030 EAL sum"
                value={
                  narrative.expected_loss.eal_2030_sum == null
                    ? "Not available"
                    : money(Number(narrative.expected_loss.eal_2030_sum), currency)
                }
                methodology={String(
                  narrative.expected_loss.horizon_method ??
                    narrative.expected_loss.methodology_version ??
                    meth?.expected_loss,
                )}
                calibration={calib}
              />
              <Metric
                label="2050 EAL sum"
                value={
                  narrative.expected_loss.eal_2050_sum == null
                    ? "Not available"
                    : money(Number(narrative.expected_loss.eal_2050_sum), currency)
                }
                methodology={String(
                  narrative.expected_loss.horizon_method ??
                    narrative.expected_loss.methodology_version ??
                    meth?.expected_loss,
                )}
                calibration={calib}
              />
            </dl>
            {narrative.expected_loss.horizon_disclaimer ? (
              <p className="pdemo-footnote" role="note">
                {String(narrative.expected_loss.horizon_disclaimer)}
                {narrative.expected_loss.horizon_scales ? (
                  <>
                    {" "}
                    Scales:{" "}
                    <code>
                      {JSON.stringify(narrative.expected_loss.horizon_scales)}
                    </code>
                  </>
                ) : null}
              </p>
            ) : null}
            <p className="pdemo-footnote">
              Damage curves:{" "}
              <code>
                {String(
                  narrative.expected_loss.damage_curves_version ?? meth?.damage_curves,
                )}
              </code>
            </p>
          </article>

          <article className="pdemo-block" data-step="adaptation">
            <h2>4. Adaptation</h2>
            <p>{String(narrative.adaptation.message ?? "")}</p>
            <dl className="pdemo-metrics">
              <Metric
                label="Top recommendation"
                value={String(narrative.adaptation.top_recommended_measure_id ?? "—")}
                methodology={String(
                  narrative.adaptation.methodology_version ?? meth?.adaptation_evidence,
                )}
                calibration={calib}
              />
            </dl>
            <ul className="pdemo-list">
              {Object.entries(
                (narrative.adaptation.recommended_measure_counts as Record<string, number>) ??
                  {},
              ).map(([measure, count]) => (
                <li key={measure}>
                  <strong>{measure}</strong>
                  <span>
                    {count} assets
                    <MethodBadge
                      methodology={String(
                        narrative.adaptation.methodology_version ?? meth?.adaptation_evidence,
                      )}
                      calibration={calib}
                    />
                  </span>
                </li>
              ))}
            </ul>
          </article>

          <article className="pdemo-block" data-step="avoided_loss">
            <h2>5. Avoided loss</h2>
            <p>{String(narrative.avoided_loss.message ?? "")}</p>
            <dl className="pdemo-metrics emphasize">
              <Metric
                label="Avoided loss (sum)"
                value={money(Number(narrative.avoided_loss.avoided_loss_sum), currency)}
                methodology={String(
                  narrative.avoided_loss.methodology_version ?? meth?.adaptation_evidence,
                )}
                calibration={calib}
              />
              <Metric
                label="Residual EAL (sum)"
                value={money(Number(narrative.avoided_loss.residual_eal_sum), currency)}
                methodology={String(
                  narrative.avoided_loss.methodology_version ?? meth?.adaptation_evidence,
                )}
                calibration={calib}
              />
              <Metric
                label="Avoided loss (mean)"
                value={money(Number(narrative.avoided_loss.avoided_loss_mean), currency)}
                methodology={String(
                  narrative.avoided_loss.methodology_version ?? meth?.adaptation_evidence,
                )}
                calibration={calib}
              />
            </dl>
          </article>

          {narrative.verification ? (
            <article className="pdemo-block pdemo-verify" id="verification" data-step="verification">
              <h2>Verification walkthrough</h2>
              <p>
                Code-isolated recompute for featured asset{" "}
                <strong>{narrative.verification.asset_id}</strong> (highest EAL). Same check as
                CI <code>verify-eal</code> — pipeline vs first-principles verifier.{" "}
                <strong>PASS means reproducibility</strong> (same inputs and versions → same
                cents-rounded result), not observational validation of loss accuracy.
              </p>
              <p className="pdemo-verify-meta">
                <span
                  className={
                    narrative.verification.agreement === "PASS"
                      ? "pdemo-agree pass"
                      : "pdemo-agree fail"
                  }
                >
                  Agreement: {narrative.verification.agreement}
                </span>
                <MethodBadge
                  methodology={narrative.verification.methodology_version}
                  calibration={narrative.verification.calibration_badge}
                />
              </p>
              <dl className="pdemo-metrics">
                <Metric
                  label="Pipeline EAL"
                  value={money(narrative.verification.pipeline_eal, currency)}
                  methodology={narrative.verification.methodology_version}
                  calibration={narrative.verification.calibration_badge}
                />
                <Metric
                  label="Recomputed EAL"
                  value={money(narrative.verification.independent_eal, currency)}
                  methodology={narrative.verification.methodology_version}
                  calibration={narrative.verification.calibration_badge}
                />
                <Metric
                  label="Combined MDR"
                  value={narrative.verification.combined_mdr.toFixed(6)}
                  methodology={narrative.verification.methodology_version}
                  calibration={narrative.verification.calibration_badge}
                />
                <Metric
                  label="Vulnerability"
                  value={narrative.verification.vulnerability.toFixed(4)}
                  methodology={narrative.verification.methodology_version}
                  calibration={narrative.verification.calibration_badge}
                />
              </dl>
              <p className="pdemo-footnote">
                Trail <code>{narrative.verification.trail_record_id}</code> · hash{" "}
                <code>{narrative.verification.trail_record_hash.slice(0, 16)}…</code>
              </p>
              <h3>Per-hazard steps</h3>
              <div className="pdemo-table-wrap">
                <table className="pdemo-table">
                  <thead>
                    <tr>
                      <th>Hazard</th>
                      <th>Intensity</th>
                      <th>Curve</th>
                      <th>MDR</th>
                      <th>Notional loss</th>
                      <th>Formula</th>
                    </tr>
                  </thead>
                  <tbody>
                    {narrative.verification.steps.map((step) => (
                      <tr key={step.hazard_id}>
                        <td>{step.hazard_id}</td>
                        <td>{pct(step.intensity)}</td>
                        <td>
                          <code>{step.curve_id}</code>
                        </td>
                        <td>{step.mdr.toFixed(6)}</td>
                        <td>{money(step.loss, currency)}</td>
                        <td>
                          <code className="pdemo-formula">{step.formula}</code>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="pdemo-footnote">
                Full sample report:{" "}
                <a
                  href={narrative.verification.sample_report_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {narrative.verification.sample_report_path}
                </a>
              </p>
            </article>
          ) : null}

          <article className="pdemo-block">
            <h2>Asset results</h2>
            <div className="pdemo-table-wrap">
              <table className="pdemo-table">
                <thead>
                  <tr>
                    <th>Asset</th>
                    <th>Type</th>
                    <th>Value</th>
                    <th>Hazard</th>
                    <th>EAL</th>
                    <th>Avoided</th>
                    <th>Residual</th>
                    <th>Measure</th>
                  </tr>
                </thead>
                <tbody>
                  {narrative.assets.slice(0, 25).map((row) => (
                    <tr key={row.asset_id}>
                      <td>
                        {row.asset_id}
                        {narrative.verification?.asset_id === row.asset_id ? (
                          <a className="pdemo-verify-link" href="#verification">
                            verify
                          </a>
                        ) : null}
                      </td>
                      <td>
                        {row.building_type} / {row.use_class}
                      </td>
                      <td>{money(row.asset_value, currency)}</td>
                      <td>{pct(row.hazard_composite)}</td>
                      <td>
                        {money(row.eal_absolute, currency)}
                        <MethodBadge
                          methodology={row.methodology_version ?? meth?.expected_loss}
                          calibration={row.calibration_badge ?? calib}
                        />
                      </td>
                      <td>
                        {money(row.avoided_loss, currency)}
                        <MethodBadge
                          methodology={meth?.adaptation_evidence}
                          calibration={calib}
                        />
                      </td>
                      <td>
                        {money(row.residual_eal, currency)}
                        <MethodBadge
                          methodology={meth?.adaptation_evidence}
                          calibration={calib}
                        />
                      </td>
                      <td>{row.recommended_measure_id ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {narrative.assets.length > 25 ? (
                <p className="pdemo-footnote">
                  Showing 25 of {narrative.assets.length} assets (full set analyzed).
                </p>
              ) : null}
            </div>
          </article>
        </section>
      ) : null}
    </main>
  );
}
