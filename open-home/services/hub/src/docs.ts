/**
 * Serves open-home's own docs as styled HTML pages, rendered from the real .md
 * files at the repo root. Allowlisted — no arbitrary path reads.
 */
import { readFile } from "node:fs/promises";
import { renderMarkdown } from "./markdown.ts";

const ROOT = new URL("../../../", import.meta.url); // repo root

export interface DocEntry { slug: string; title: string; file: string; blurb: string; }

export const DOCS: DocEntry[] = [
  { slug: "brand", title: "Brand", file: "BRAND.md", blurb: "Identity, voice, logo, and palette." },
  { slug: "business", title: "Business Plan", file: "BUSINESS_PLAN.md", blurb: "Market, model, catalog, and go-to-market." },
  { slug: "roadmap", title: "Roadmap", file: "ROADMAP.md", blurb: "What's built vs. planned, in phases." },
  { slug: "concepts", title: "Concepts", file: "CONCEPTS.md", blurb: "Experimental product ideas — the Pod." },
  { slug: "readme", title: "Overview", file: "README.md", blurb: "What open-home is and why." },
  { slug: "architecture", title: "Architecture", file: "ARCHITECTURE.md", blurb: "How the pieces fit together." },
  { slug: "hardware", title: "Hardware", file: "hardware/reference-spec.md", blurb: "The open-home box, three tiers." },
  { slug: "build", title: "Build Guide", file: "hardware/openhome-mini-build-guide.md", blurb: "Build the mini — a local \"Alexa\" on a Pi 4, with parts links." },
  { slug: "pod-mesh", title: "Pod Mesh", file: "hardware/openhome-pod-mesh.md", blurb: "Wall-plug pods in every room — agent everywhere, synced music, intercom." },
  { slug: "sound", title: "Sound", file: "services/speaker/DESIGN.md", blurb: "Speaker service + music app — zones, surround, Spotify. Design + tracker." },
  { slug: "contributing", title: "Contributing", file: "CONTRIBUTING.md", blurb: "Ground rules and dev setup." },
];

function page(title: string, body: string, nav: string): string {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<title>${title} · openhome</title>
<link rel="icon" type="image/svg+xml" href="/assets/brand/favicon.svg"/>
<meta name="theme-color" content="#0e1014"/>
<style>
  :root{--bg:#0e1014;--panel:#171a21;--panel2:#1e222b;--line:#272c37;--text:#e7ebf3;--muted:#8b93a7;--accent:#3ddc97;--accent-dim:#1f7a56}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
  header{display:flex;align-items:center;gap:12px 14px;flex-wrap:wrap;padding:calc(env(safe-area-inset-top,0px) + 14px) 24px 12px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#141821,var(--bg))}
  .brand{font-weight:700;font-size:18px;letter-spacing:-.02em}
  .brand a{color:var(--text);text-decoration:none}
  nav{display:flex;gap:6px;flex-wrap:wrap}
  nav a{color:var(--muted);text-decoration:none;font-size:14px;font-weight:600;padding:6px 11px;border-radius:999px;border:1px solid transparent}
  nav a:hover{color:var(--text);background:var(--panel2);border-color:var(--line)}
  nav a.active{color:var(--accent);border-color:var(--accent-dim);background:rgba(61,220,151,.08)}
  main{max-width:820px;margin:0 auto;padding:28px 24px 64px}
  h1{font-size:30px;letter-spacing:-.02em;margin:.2em 0 .6em}
  h2{font-size:21px;margin:1.6em 0 .5em;padding-bottom:.3em;border-bottom:1px solid var(--line)}
  h3{font-size:16px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin:1.4em 0 .4em}
  a{color:var(--accent)}
  code{background:var(--panel2);border:1px solid var(--line);padding:1px 6px;border-radius:6px;font-size:.9em}
  pre{background:#0a0c10;border:1px solid var(--line);border-radius:12px;padding:14px 16px;overflow-x:auto}
  pre code{background:none;border:0;padding:0}
  table{border-collapse:collapse;width:100%;margin:1em 0;font-size:14px}
  th,td{border:1px solid var(--line);padding:8px 12px;text-align:left;vertical-align:top}
  th{background:var(--panel2)}
  blockquote{margin:1em 0;padding:.4em 1em;border-left:3px solid var(--accent-dim);background:var(--panel);color:var(--muted);border-radius:0 8px 8px 0}
  hr{border:0;border-top:1px solid var(--line);margin:2em 0}
  img{max-width:100%;height:auto;border-radius:14px;border:1px solid var(--line);margin:1em 0;display:block;box-shadow:0 8px 30px rgba(0,0,0,.35)}
  .gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin:1.4em 0}
  .gallery img{margin:0;width:100%;height:100%;object-fit:cover;aspect-ratio:4/3}
  figure{margin:1.4em 0}figure img{margin:0}figcaption{color:var(--muted);font-size:13px;margin-top:6px;text-align:center}
  ul,ol{padding-left:1.4em}
  li{margin:.25em 0}
  .back{display:inline-block;margin-bottom:18px;color:var(--muted);text-decoration:none;font-size:14px}
  .back:hover{color:var(--accent)}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:8px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;text-decoration:none;color:var(--text)}
  .card:hover{border-color:var(--accent-dim)}
  .card h3{color:var(--accent);text-transform:none;letter-spacing:0;font-size:16px;margin:0 0 6px}
  .card p{margin:0;color:var(--muted);font-size:14px}
  @media(max-width:640px){
    header{padding:calc(env(safe-area-inset-top,0px) + 10px) 16px 8px;gap:8px 12px}
    nav{order:3;width:100%;flex-wrap:nowrap;overflow-x:auto;gap:6px;margin:2px -16px 0;padding:2px 16px 4px;-webkit-overflow-scrolling:touch;scrollbar-width:none}
    nav::-webkit-scrollbar{display:none}
    nav a{white-space:nowrap}
    body{font-size:15px}
    main{padding:20px 16px 56px}
    h1{font-size:24px}h2{font-size:19px}
    pre{border-radius:10px;padding:12px}
    /* wide tables scroll instead of squishing */
    table{display:block;overflow-x:auto;white-space:nowrap;-webkit-overflow-scrolling:touch}
  }
</style></head>
<body>
<header>
  <div class="brand"><a href="/"><img src="/assets/brand/logo.svg" alt="openhome" height="26" style="display:block"/></a></div>
  <nav>${nav}</nav>
</header>
<main>${body}</main>
</body></html>`;
}

function navHtml(active: string): string {
  const items = [`<a href="/"${active === "dash" ? ' class="active"' : ""}>Dashboard</a>`];
  for (const d of DOCS) items.push(`<a href="/docs/${d.slug}"${active === d.slug ? ' class="active"' : ""}>${d.title}</a>`);
  return items.join("");
}

export function docsIndexHtml(): string {
  const cards = DOCS.map((d) =>
    `<a class="card" href="/docs/${d.slug}"><h3>${d.title}</h3><p>${d.blurb}</p></a>`).join("");
  return page("Docs", `<a class="back" href="/">← Dashboard</a><h1>Docs</h1><div class="cards">${cards}</div>`, navHtml("docs"));
}

export async function docPageHtml(slug: string): Promise<string | null> {
  const entry = DOCS.find((d) => d.slug === slug);
  if (!entry) return null;
  const md = await readFile(new URL(entry.file, ROOT), "utf8");
  const body = `<a class="back" href="/docs">← All docs</a>` + renderMarkdown(md);
  return page(entry.title, body, navHtml(slug));
}
