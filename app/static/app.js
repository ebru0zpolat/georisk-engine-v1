const assetSelect = document.querySelector("#asset-select");
const runButton = document.querySelector("#run-button");
const statusText = document.querySelector("#status");
const results = document.querySelector("#results");
const downloadLink = document.querySelector("#download-link");

const score = document.querySelector("#score");
const band = document.querySelector("#band");
const headline = document.querySelector("#headline");
const assetName = document.querySelector("#asset-name");
const assetMeta = document.querySelector("#asset-meta");
const components = document.querySelector("#components");
const flags = document.querySelector("#flags");
const interpretation = document.querySelector("#interpretation");

async function fetchJson(url) {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return response.json();
}

function setStatus(message, isError = false) {
  statusText.textContent = message;
  statusText.classList.toggle("error", isError);
}

function renderComponents(componentScores) {
  components.replaceChildren(
    ...Object.entries(componentScores).map(([name, value]) => {
      const item = document.createElement("div");
      item.className = "component";

      const label = document.createElement("span");
      label.textContent = name.replace("_", " ");

      const number = document.createElement("strong");
      number.textContent = value;

      item.append(label, number);
      return item;
    })
  );
}

function renderFlags(items) {
  const visibleFlags = items.length > 0 ? items : ["None"];
  flags.replaceChildren(
    ...visibleFlags.map((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      return li;
    })
  );
}

function renderResult(data) {
  score.textContent = `${data.summary.overall_score}/100`;
  band.textContent = data.summary.risk_band;
  headline.textContent = data.summary.headline;
  assetName.textContent = data.asset.name;
  assetMeta.textContent = `${data.asset.sector} | ${data.asset.latitude}, ${data.asset.longitude} | ${data.asset.radius_km} km radius`;
  interpretation.textContent = data.interpretation;

  renderComponents(data.components);
  renderFlags(data.flags);

  downloadLink.href = `/v1/demo/run/pdf?asset_id=${encodeURIComponent(assetSelect.value)}`;
  downloadLink.classList.remove("hidden");
  results.classList.remove("hidden");
}

async function loadAssets() {
  try {
    const assets = await fetchJson("/v1/demo/assets");

    assetSelect.replaceChildren(
      ...assets.map((asset) => {
        const option = document.createElement("option");
        option.value = asset.id;
        option.textContent = asset.name;
        return option;
      })
    );

    setStatus("Choose an asset and run the assessment.");
  } catch (error) {
    setStatus(error.message, true);
    runButton.disabled = true;
  }
}

async function runAssessment() {
  runButton.disabled = true;
  setStatus("Running assessment...");

  try {
    const data = await fetchJson(`/v1/demo/run?asset_id=${encodeURIComponent(assetSelect.value)}`);
    renderResult(data);
    setStatus(`Generated audit ${data.audit.audit_id}.`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    runButton.disabled = false;
  }
}

runButton.addEventListener("click", runAssessment);
loadAssets();
