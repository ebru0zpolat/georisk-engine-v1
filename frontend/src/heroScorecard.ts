import { CLAIM_STATES, type ClaimState } from "./claimStates";
import { computePreviewRiskScore, type PreviewRiskScorecard } from "./computePreviewRiskScore";

/**
 * Wires the landing hero's coordinate box to the real 1-minute scorecard
 * (UC-01, POST /v1/risk/preview).
 *
 * Claim discipline: the endpoint returns an indicative composite over climate
 * and satellite proxies and does not report a per-component claim state, so
 * every value rendered here is labelled MODELLED. It is never upgraded to
 * VERIFIED or LIVE on the strength of the call having succeeded, and the
 * endpoint's own disclaimer is rendered verbatim beside the score.
 */

const RESULT_ID = "heroResult";

function chip(state: ClaimState): HTMLElement {
  const spec = CLAIM_STATES[state];
  const el = document.createElement("span");
  el.className = "claim-chip claim-chip-sm";
  el.dataset.claimState = state;
  el.title = spec.tooltip;

  const icon = document.createElement("span");
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = spec.icon;

  const label = document.createElement("span");
  label.textContent = spec.label;

  el.append(icon, label);
  return el;
}

function el(tag: string, className?: string, text?: string): HTMLElement {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function bandClass(band: string): string {
  const b = band.toLowerCase();
  if (b.includes("high") || b.includes("yüksek")) return "risk-high";
  if (b.includes("medium") || b.includes("orta")) return "risk-med";
  return "risk-low";
}

function renderScorecard(target: HTMLElement, data: PreviewRiskScorecard): void {
  target.replaceChildren();

  const head = el("div", "hero-result-head");
  const title = el("div");
  title.append(
    el("div", "hero-result-name", data.resolved.asset_name),
    el(
      "div",
      "hero-result-coords",
      `${data.resolved.latitude}, ${data.resolved.longitude} · ${data.resolved.radius_km} km · ${data.resolved.resolution_method}`,
    ),
  );

  const scoreBox = el("div", "hero-result-score");
  scoreBox.append(
    el(
      "strong",
      bandClass(data.risk_band),
      String(data.indicative_climate_risk_score),
    ),
    el("span", "risk-badge " + bandClass(data.risk_band), `${data.risk_band} risk`),
    chip("MODELLED"),
  );

  head.append(title, scoreBox);
  target.append(head);

  if (data.headline) target.append(el("p", "hero-result-headline", data.headline));

  if (data.components.length) {
    const grid = el("div", "hero-result-components");
    for (const component of data.components) {
      const row = el("div", "hero-result-component");
      row.append(
        el("span", "hero-result-component-label", component.label),
        chip("MODELLED"),
        el("strong", bandClass(component.score >= 70 ? "high" : component.score >= 45 ? "medium" : "low"), String(component.score)),
      );
      grid.append(row);
    }
    target.append(grid);
  }

  if (data.top_flags.length) {
    const flags = el("div", "hero-result-flags");
    for (const flag of data.top_flags) flags.append(el("span", "cell-tag", flag));
    target.append(flags);
  }

  target.append(el("p", "hero-result-disclaimer", data.disclaimer));
  target.append(el("p", "hero-result-audit", `audit_id ${data.audit_id}`));

  target.hidden = false;
}

function renderError(target: HTMLElement, message: string): void {
  target.replaceChildren();
  target.append(el("p", "hero-result-error", message));
  target.hidden = false;
}

export function initHeroScorecard(): void {
  // The landing markup is present but hidden on SPA routes; do not bind there.
  if (document.body.classList.contains("spa-app")) return;

  const input = document.getElementById("heroInput") as HTMLInputElement | null;
  const button = document.getElementById("heroSubmit") as HTMLButtonElement | null;
  const result = document.getElementById(RESULT_ID);
  if (!input || !button || !result) return;

  let running = false;

  async function run(): Promise<void> {
    if (running || !input || !button || !result) return;
    const location = input.value.trim();
    if (!location) {
      input.focus();
      return;
    }

    running = true;
    const label = button.textContent;
    button.disabled = true;
    button.textContent = "Scoring…";
    result.hidden = false;
    result.replaceChildren(el("p", "hero-result-status", "Scoring location…"));

    try {
      const data = await computePreviewRiskScore({ location });
      renderScorecard(result, data);
    } catch (error) {
      renderError(
        result,
        error instanceof Error
          ? `Could not score that location: ${error.message}`
          : "Could not score that location.",
      );
    } finally {
      running = false;
      button.disabled = false;
      button.textContent = label;
    }
  }

  button.addEventListener("click", () => void run());
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void run();
    }
  });
}
