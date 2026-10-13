import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { spawn } from "node:child_process";

function visibleText(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function countTerm(body, term) {
  return body.toLowerCase().split(term.toLowerCase()).length - 1;
}

function requireDensity(label, body, term, min, max = Infinity) {
  const count = countTerm(body, term);
  if (count < min || count > max) {
    throw new Error(`${label} must contain ${term} between ${min} and ${max} times, got ${count}`);
  }
}

const distDir = new URL("../dist/", import.meta.url);
const vercelConfig = JSON.parse(readFileSync(new URL("../vercel.json", import.meta.url), "utf8"));

const requiredFiles = [
  {
    path: "robots.txt",
    includes: ["User-agent: *", "Sitemap: https://georiskengine.com/sitemap.xml"],
    forbidden: ["<!doctype html", "<html"],
  },
  {
    path: "sitemap.xml",
    includes: [
      "<urlset",
      "https://georiskengine.com/",
      "<priority>1.0</priority>",
      "https://georiskengine.com/services",
      "<priority>0.9</priority>",
      "https://georiskengine.com/services/tsrs-compliance",
      "<priority>0.8</priority>",
      "https://georiskengine.com/methodology",
    ],
    forbidden: [
      "<!doctype html",
      "https://georiskengine.com/hizmetler",
      "https://georiskengine.com/blog/tsrs-compliance-guide",
      "https://georiskengine.com/konum-zekasi-platformu",
      "https://georiskengine.com/lokasyon-risk-analizi-araclari",
      "https://georiskengine.com/georisk-engine-ozellikleri",
      "https://georiskengine.com/iklim-riski-fiyatlandirma",
      "https://georiskengine.com/konum-zekasi-cevresel-risk-yonetimi",
    ],
  },
  {
    path: "methodology.html",
    includes: [
      "georisk-methodology-v0.4.0",
      "August 2026",
      "Phase A Scenario-Loss Proxy",
      "1 − Π(1 − MDR)",
      "Recomputed EAL",
      "intended to support selected physical-risk assessment",
      "must not be used as the sole basis for automated lending or investment decisions",
      "Evidence gaps before v1.0",
      "v1.0 / banka pilotu öncesi kanıt boşlukları",
      "Sürüm yol haritası (temalar)",
      "Düzenleyici referans notları",
      "Kanonik kaynaklar",
      'id="lang-switch"',
      'id="btn-en"',
      'id="btn-tr"',
      'class="i18n-en"',
      'class="i18n-tr"',
      "Ön Metodoloji ve Doğrulama Planı",
      "Sentetik Kalibrasyon v0.4.0",
      "yegâne dayanağı olarak kullanılmamalıdır",
      "GEORISK_ENGINE_METHODOLOGY.md",
      "Flood",
      "extreme heat",
    ],
    forbidden: [
      "6hr Pipeline ingest",
      "Validated methodology",
      "Regulatory-compliant model",
      "Independent verification completed",
      "Bank-grade",
      "Predicts credit losses",
      "to the cent",
      // Old decision-use wording without "sole basis" (substring-safe vs corrected copy)
      "must not be used as automated lending or investment decisions.",
    ],
  },
  {
    path: "_redirects",
    includes: ["/sustainability-reporting-standards-turkey-tsrs /services/tsrs-compliance 301"],
    // No catch-all: Cloudflare Pages serves index.html for unmatched paths
    // itself when dist/ has no 404.html (checked below).
    forbidden: ["/* /index.html 200"],
  },
  {
    path: "hizmetler.html",
    includes: [
      "Reference Frameworks",
      "Bu metodolojiyi kim doğruladı?",
      "IPCC Scenarios",
      "ESA / Copernicus",
      "not endorsement",
      "Geospatial Risk Intelligence Platformu",
      "Geospatial hub target audience",
      "Konum Zekası",
      "Risk Puanlama",
      "Uydu Verisi",
      "TSRS 1 / TSRS 2 terminology alignment",
      "methodologically transparent",
      "scientifically validated",
      "peer-reviewed data protocols",
    ],
    forbidden: ["Audit-Ready", "audit-ready", "reviewable validation"],
  },
  {
    path: "konum-zekasi-platformu.html",
    includes: ["Fan-out query answer"],
    forbidden: [],
  },
  {
    path: "lokasyon-risk-analizi-araclari.html",
    includes: ["Fan-out query answer"],
    forbidden: [],
  },
  {
    path: "georisk-engine-ozellikleri.html",
    includes: ["Fan-out query answer"],
    forbidden: [],
  },
  {
    path: "iklim-riski-fiyatlandirma.html",
    includes: ["Fan-out query answer"],
    forbidden: [],
  },
  {
    path: "konum-zekasi-cevresel-risk-yonetimi.html",
    includes: [
      "Konum Zekası (Location Intelligence) ile Çevresel Risk Yönetimi Nasıl Yapılır?",
      "Konum zekası ile çevresel risk yönetimi nasıl yapılır sorusunu destekleyen İstanbul Marmara Bölgesi sismik risk yoğunluk haritası analizi - GeoRisk Engine",
      "TSRS 1 genel sürdürülebilirlik açıklamaları",
      "TSRS 2 iklimle ilgili açıklamalar",
    ],
    forbidden: [],
  },
  {
    path: "services.html",
    includes: [
      "Reference Frameworks",
      "IPCC Scenarios",
      "ESA / Copernicus",
      "Peer-reviewed data protocols",
      "not claim third-party certification",
      "BreadcrumbList",
      "\"name\": \"Services\"",
      "https://georiskengine.com/services",
      "Get a 1-Minute Risk Scorecard",
      "Indicative Climate Risk Score",
      "Coordinate or address",
      "computePreviewRiskScore",
      "Geospatial Intelligence Services for Industrial Risk",
      "geospatial intelligence",
      "satellite-based indicators",
      "Geospatial intelligence services target audience",
      "\"@type\": \"FAQPage\"",
    ],
    forbidden: [],
  },
  {
    path: "services/tsrs-compliance.html",
    includes: [
      "TSRS Compliance Turkey Services",
      "Turkish Sustainability Reporting Standards (TSRS)",
      "Public Oversight Authority of Turkey (KGK)",
      "IFRS S2",
      "ISSB",
      "KGK Audit",
      "Climate Risk Reporting for TSRS 2",
      "Requirement",
      "Global Reference (IFRS)",
      "Local Mandate (TSRS/KGK)",
      "What does a TSRS 2 physical risk report deliverable look like?",
      "TSRS 2 compliant sample physical climate risk report page showing facility exposure score, KGK audit evidence, satellite indicators and methodology notes - GeoRisk Engine",
      "tsrs-2-physical-risk-report-mockup.svg",
      "\"@type\": \"Organization\"",
      "\"knowsAbout\": [",
      "\"TSRS\"",
      "\"KGK\"",
      "\"IFRS S2\"",
      "\"Climate Risk Quantification\"",
      "\"@type\": \"Service\"",
      "\"Climate Risk Reporting for TSRS 2\"",
      "\"@type\": \"FAQPage\"",
      "How to comply with KGK mandates?",
      "/blog/tsrs-compliance-guide",
    ],
    forbidden: ["\"@type\": \"BlogPosting\""],
  },
  {
    path: "blog/tsrs-compliance-guide.html",
    includes: [
      "TSRS Reporting Framework Guide",
      "https://georiskengine.com/blog/tsrs-compliance-guide",
      "TSRS (Turkish Sustainability Reporting Standards)",
      "KGK (Public Oversight Authority of Turkey)",
      "TSRS Reporting Framework",
      "Aligning with TSRS Standards",
      "TSRS Disclosure Requirements",
      "\"@type\": \"FAQPage\"",
      "\"@type\": \"BlogPosting\"",
    ],
    forbidden: ["TSRS Compliance Turkey", "TSRS Compliance"],
  },
  {
    path: "images/tsrs-2-physical-risk-report-mockup.svg",
    includes: [
      "TSRS 2 Physical Climate Risk Report",
      "KGK audit evidence",
      "Deliverable: one-page TSRS 2 physical risk summary",
    ],
    forbidden: [],
  },
];

for (const file of requiredFiles) {
  const absolutePath = join(distDir.pathname, file.path);
  statSync(absolutePath);
  const body = readFileSync(absolutePath, "utf8");
  const lowerBody = body.toLowerCase();

  for (const expected of file.includes) {
    if (!body.includes(expected)) {
      throw new Error(`${file.path} is missing expected content: ${expected}`);
    }
  }

  for (const forbidden of file.forbidden) {
    if (lowerBody.includes(forbidden)) {
      throw new Error(`${file.path} appears to contain fallback HTML`);
    }
  }
}

const tsrsServiceBody = readFileSync(new URL("../dist/services/tsrs-compliance.html", import.meta.url), "utf8");
const firstTsrsFull = tsrsServiceBody.indexOf("Turkish Sustainability Reporting Standards (TSRS)");
const firstTsrsShort = tsrsServiceBody.indexOf("TSRS");
if (firstTsrsFull === -1 || firstTsrsShort !== firstTsrsFull + "Turkish Sustainability Reporting Standards (".length) {
  throw new Error("/services/tsrs-compliance must first use TSRS as Turkish Sustainability Reporting Standards (TSRS)");
}
const firstKgkFull = tsrsServiceBody.indexOf("Public Oversight Authority of Turkey (KGK)");
const firstKgkShort = tsrsServiceBody.indexOf("KGK");
if (firstKgkFull === -1 || firstKgkShort !== firstKgkFull + "Public Oversight Authority of Turkey (".length) {
  throw new Error("/services/tsrs-compliance must first use KGK as Public Oversight Authority of Turkey (KGK)");
}

const hizmetlerBodyForComplianceCheck = readFileSync(new URL("../dist/hizmetler.html", import.meta.url), "utf8");
const hizmetlerForbiddenCompliancePattern = /audit-ready|reviewable validation/i;
if (hizmetlerForbiddenCompliancePattern.test(hizmetlerBodyForComplianceCheck)) {
  throw new Error("Forbidden compliance keywords found in /hizmetler!");
}
console.log("Hizmetler page is clean and focused on technical methodology.");

const blogBody = readFileSync(new URL("../dist/blog/tsrs-compliance-guide.html", import.meta.url), "utf8");
const blogCanonicalUrl = "https://georiskengine.com/blog/tsrs-compliance-guide";
if (!blogBody.includes(`<link rel="canonical" href="${blogCanonicalUrl}">`)) {
  throw new Error("TSRS blog must self-canonicalize to /blog/tsrs-compliance-guide");
}
const blogJsonLdBlocks = [...blogBody.matchAll(/<script type="application\/ld\+json">\s*([\s\S]*?)\s*<\/script>/g)].map((match) => JSON.parse(match[1]));
const blogPosting = blogJsonLdBlocks.find((block) => block["@type"] === "BlogPosting");
if (!blogPosting) {
  throw new Error("TSRS blog must include BlogPosting JSON-LD");
}
if (blogPosting.mainEntityOfPage?.["@type"] !== "WebPage" || blogPosting.mainEntityOfPage?.["@id"] !== blogCanonicalUrl) {
  throw new Error("TSRS blog BlogPosting must use mainEntityOfPage WebPage object for its canonical URL");
}
const servicesPageBody = readFileSync(new URL("../dist/services.html", import.meta.url), "utf8");
for (const forbiddenServicesTerm of [
  "TSRS Compliance Turkey",
  "TSRS (Turkish Sustainability Reporting Standards)",
  "KGK (Public Oversight Authority of Turkey)",
]) {
  if (servicesPageBody.includes(forbiddenServicesTerm)) {
    throw new Error(`/services must not compete with TSRS blog/service term: ${forbiddenServicesTerm}`);
  }
}


// Compliance/Audit density rules for services and reporting/guidance pages.
const servicesVisibleText = visibleText(servicesPageBody);
const hizmetlerBody = readFileSync(new URL("../dist/hizmetler.html", import.meta.url), "utf8");
const hizmetlerVisibleText = visibleText(hizmetlerBody);
const blogVisibleText = visibleText(blogBody);

requireDensity("/services", servicesVisibleText, "Compliance", 5);
requireDensity("/services", servicesVisibleText, "Audit", 10);
requireDensity("/hizmetler", hizmetlerVisibleText, "Reporting", 5);
requireDensity("/hizmetler", hizmetlerVisibleText, "Validation", 5);
requireDensity("/hizmetler", hizmetlerVisibleText, "Guidelines", 3);
requireDensity("/hizmetler", hizmetlerVisibleText, "Compliance", 0, 1);
requireDensity("/blog/tsrs-compliance-guide", blogVisibleText, "Reporting", 10);
requireDensity("/blog/tsrs-compliance-guide", blogVisibleText, "Validation", 3);
requireDensity("/blog/tsrs-compliance-guide", blogVisibleText, "Guidelines", 3);
requireDensity("/blog/tsrs-compliance-guide", blogVisibleText, "Compliance", 1, 4);
if (!blogBody.includes('<a href="/services">TSRS Compliance Turkey</a>')) {
  throw new Error('TSRS blog must pass authority with exact internal link text: <a href="/services">TSRS Compliance Turkey</a>');
}


function jsonLdBlocks(html) {
  return [...html.matchAll(/<script type="application\/ld\+json">\s*([\s\S]*?)\s*<\/script>/g)].map((match) => JSON.parse(match[1]));
}

function validateBreadcrumb(pagePath, expectedNames, expectedUrls) {
  const html = readFileSync(new URL(`../dist/${pagePath}.html`, import.meta.url), "utf8");
  const breadcrumb = jsonLdBlocks(html).find((block) => block["@type"] === "BreadcrumbList");
  if (!breadcrumb) {
    throw new Error(`${pagePath} must include BreadcrumbList JSON-LD`);
  }
  const items = breadcrumb.itemListElement ?? [];
  const names = items.map((item) => item.name);
  const urls = items.map((item) => item.item);
  if (JSON.stringify(names) !== JSON.stringify(expectedNames) || JSON.stringify(urls) !== JSON.stringify(expectedUrls)) {
    throw new Error(`${pagePath} breadcrumb mismatch: ${JSON.stringify({ names, urls })}`);
  }
}

validateBreadcrumb("services", ["Home", "Services"], ["https://georiskengine.com/", "https://georiskengine.com/services"]);
validateBreadcrumb("services/tsrs-compliance", ["Home", "Services", "TSRS Compliance"], ["https://georiskengine.com/", "https://georiskengine.com/services", "https://georiskengine.com/services/tsrs-compliance"]);

const servicesBody = readFileSync(new URL("../dist/services.html", import.meta.url), "utf8");
const serviceSummaryMatches = [...servicesBody.matchAll(/<section id="atomic-service-summaries">[\s\S]*?<\/section>/g)];
if (!serviceSummaryMatches.length) {
  throw new Error("services page must include atomic-service-summaries section");
}
const summaryTexts = [...serviceSummaryMatches[0][0].matchAll(/<article class="card"><h3>[^<]+<\/h3><p>([^<]+)<\/p><\/article>/g)].map((match) => match[1]);
if (summaryTexts.length !== 5) {
  throw new Error("services page must include five atomic service summaries");
}
const summary_counts_45_49 = summaryTexts.map((text) => text.split(/\s+/).filter(Boolean).length);
if (!summary_counts_45_49.every((count) => count >= 45 && count <= 49)) {
  throw new Error(`services atomic summaries must be 45-49 words, got ${summary_counts_45_49.join(", ")}`);
}

const sitemapBody = readFileSync(new URL("../dist/sitemap.xml", import.meta.url), "utf8");
const locMatches = [...sitemapBody.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) => match[1]);
const expectedLocs = [
  "https://georiskengine.com/",
  "https://georiskengine.com/services",
  "https://georiskengine.com/services/tsrs-compliance",
  "https://georiskengine.com/methodology",
  "https://georiskengine.com/blog/",
  "https://georiskengine.com/blog/cbam-dogrulanabilir-karbon-verisi",
  "https://georiskengine.com/contact",
];
if (JSON.stringify(locMatches) !== JSON.stringify(expectedLocs)) {
  throw new Error(`sitemap.xml must contain only ${expectedLocs.join(", ")}; got ${locMatches.join(", ")}`);
}

for (const [loc, priority] of [
  ["https://georiskengine.com/", "1.0"],
  ["https://georiskengine.com/services", "0.9"],
  ["https://georiskengine.com/services/tsrs-compliance", "0.8"],
  ["https://georiskengine.com/methodology", "0.8"],
  ["https://georiskengine.com/blog/", "0.7"],
  ["https://georiskengine.com/blog/cbam-dogrulanabilir-karbon-verisi", "0.6"],
  ["https://georiskengine.com/contact", "0.5"],
]) {
  const priorityPattern = new RegExp(`<loc>${loc.replace(/\//g, "\/").replace(/\./g, "\.")}</loc>\n    <lastmod>2026-08-14</lastmod>\n    <priority>${priority.replace(".", "\.")}</priority>`);
  if (!priorityPattern.test(sitemapBody)) {
    throw new Error(`sitemap.xml must assign priority ${priority} to ${loc}`);
  }
}

if (vercelConfig.cleanUrls !== true) {
  throw new Error("vercel.json must set cleanUrls: true");
}

const rewrites = vercelConfig.rewrites ?? [];
const staticPassthrough = rewrites.findIndex(
  (rewrite) => rewrite.source === "/(robots.txt|sitemap.xml|_redirects)" && rewrite.destination === "/$1",
);
// With cleanUrls: true, SPA destinations must omit .html (Vercel docs → "/").
const spaFallback = rewrites.findIndex(
  (rewrite) => rewrite.source === "/(.*)" && rewrite.destination === "/",
);

if (staticPassthrough !== 0) {
  throw new Error("vercel.json must keep static asset passthrough as the first rewrite");
}

if (spaFallback !== rewrites.length - 1) {
  throw new Error("vercel.json must keep SPA fallback as the final rewrite");
}

const cleanUrlPages = [
  "hizmetler",
  "blog/tsrs-compliance-guide",
  "services/tsrs-compliance",
  "services",
  "methodology",
  "konum-zekasi-platformu",
  "lokasyon-risk-analizi-araclari",
  "georisk-engine-ozellikleri",
  "iklim-riski-fiyatlandirma",
  "konum-zekasi-cevresel-risk-yonetimi",
];

for (const page of cleanUrlPages) {
  const pageRewrite = rewrites.findIndex(
    (rewrite) => rewrite.source === `/${page}` && rewrite.destination === `/${page}`,
  );

  if (pageRewrite === -1) {
    throw new Error(`vercel.json must rewrite /${page} to /${page} (cleanUrls, no .html)`);
  }

  if (!(staticPassthrough < pageRewrite && pageRewrite < spaFallback)) {
    throw new Error(`vercel.json rewrite for /${page} must appear between static passthrough and SPA fallback`);
  }

  // Cloudflare Pages 308-redirects /<page> to /<page>/ for a directory index;
  // scripts/flatten-clean-urls.mjs must have emitted <page>.html instead.
  statSync(new URL(`../dist/${page}.html`, import.meta.url));
  if (existsSync(new URL(`../dist/${page}/index.html`, import.meta.url))) {
    throw new Error(`dist/${page}/index.html must be flattened to dist/${page}.html (run scripts/flatten-clean-urls.mjs)`);
  }
}

// A top-level 404.html switches Cloudflare Pages out of SPA mode, so /demo,
// /tiles and /snapshot/* would 404 instead of loading the app shell.
if (existsSync(new URL("../dist/404.html", import.meta.url))) {
  throw new Error("dist/404.html must not exist: it disables the Cloudflare Pages SPA fallback");
}

for (const spaPath of ["/demo", "/tiles"]) {
  const spaRewrite = rewrites.find(
    (rewrite) => rewrite.source === spaPath && rewrite.destination === "/",
  );
  if (!spaRewrite) {
    throw new Error(`vercel.json must rewrite ${spaPath} to / for the SPA shell`);
  }
}

const legacyTsrsRedirect = vercelConfig.redirects?.some(
  (redirect) => redirect.source === "/sustainability-reporting-standards-turkey-tsrs"
    && redirect.destination === "/services/tsrs-compliance"
    && redirect.permanent === true,
);

if (!legacyTsrsRedirect) {
  throw new Error("vercel.json must permanently redirect legacy TSRS blog URL to /services/tsrs-compliance");
}

async function verifyPreviewHeaders() {
  const preview = spawn("npm", ["run", "preview", "--", "--host", "127.0.0.1", "--port", "4179"], {
    cwd: new URL("..", import.meta.url).pathname,
    detached: true,
    stdio: "ignore",
  });
  preview.unref();

  const pid = preview.pid;
  try {
    const deadline = Date.now() + 5000;
    let robotsType = "";
    let sitemapType = "";
    while (Date.now() < deadline) {
      try {
        const robotsResponse = await fetch("http://127.0.0.1:4179/robots.txt");
        const sitemapResponse = await fetch("http://127.0.0.1:4179/sitemap.xml");
        robotsType = robotsResponse.headers.get("content-type") ?? "";
        sitemapType = sitemapResponse.headers.get("content-type") ?? "";
        if (robotsResponse.ok && sitemapResponse.ok) break;
      } catch {
        // Preview server may still be starting.
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    if (!robotsType.includes("text/plain")) {
      throw new Error(`preview /robots.txt must be text/plain, got ${robotsType || "missing content-type"}`);
    }

    if (!(sitemapType.includes("application/xml") || sitemapType.includes("text/xml"))) {
      throw new Error(`preview /sitemap.xml must be XML content-type, got ${sitemapType || "missing content-type"}`);
    }
  } finally {
    if (pid) {
      try {
        process.kill(-pid);
      } catch {
        // Ignore cleanup failures.
      }
    }
  }
}

if (process.env.VERIFY_PREVIEW_HEADERS === "1") {
  await verifyPreviewHeaders();
}

console.log("Public asset verification passed.");
