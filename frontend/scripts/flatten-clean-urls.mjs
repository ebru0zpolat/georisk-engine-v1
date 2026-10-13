// Post-build: move dist/<page>/index.html to dist/<page>.html when the page's
// canonical URL has no trailing slash.
//
// Cloudflare Pages answers /<page> with a 308 to /<page>/ when only
// <page>/index.html exists, which contradicts the slash-less canonical URLs
// and sitemap entries. As <page>.html it is served at /<page> directly (and
// Vercel's cleanUrls serves it the same way). Pages whose canonical ends in
// "/" (e.g. /blog/) keep the directory layout.
import { existsSync, readdirSync, readFileSync, renameSync, rmdirSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const distDir = join(dirname(fileURLToPath(import.meta.url)), "..", "dist");

function findIndexFiles(dir) {
  const found = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) found.push(...findIndexFiles(full));
    else if (entry.name === "index.html" && dir !== distDir) found.push(full);
  }
  return found;
}

function canonicalHref(html, file) {
  const match = html.match(/<link rel="canonical" href="([^"]+)"/);
  if (!match) throw new Error(`${file}: no canonical link; cannot decide its URL form`);
  return match[1];
}

if (!existsSync(distDir)) throw new Error(`dist/ not found at ${distDir}; run vite build first`);

let moved = 0;
// Deepest first, so services/tsrs-compliance moves before services.
for (const indexFile of findIndexFiles(distDir).sort((a, b) => b.split(sep).length - a.split(sep).length)) {
  const pageDir = dirname(indexFile);
  const label = relative(distDir, indexFile);
  if (canonicalHref(readFileSync(indexFile, "utf8"), label).endsWith("/")) continue;

  const target = `${pageDir}.html`;
  if (existsSync(target)) throw new Error(`${label}: ${relative(distDir, target)} already exists`);
  renameSync(indexFile, target);
  if (readdirSync(pageDir).length === 0) rmdirSync(pageDir);
  console.log(`flatten-clean-urls: ${label} -> ${relative(distDir, target)}`);
  moved += 1;
}
console.log(`flatten-clean-urls: ${moved} page(s) flattened`);
