/**
 * Tiny, dependency-free Markdown → HTML renderer.
 *
 * Intentionally small: enough to render open-home's own docs (headings, lists,
 * tables, code fences, blockquotes, inline emphasis/links). Not a spec-complete
 * parser. Input is our own trusted files, but we HTML-escape anyway.
 */

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function inline(s: string): string {
  return esc(s)
    .replace(/`([^`]+)`/g, (_m, c) => `<code>${c}</code>`)
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_m, alt, src) => `<img src="${src}" alt="${alt}" loading="lazy"/>`)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, t, href) => `<a href="${href}" target="_blank" rel="noopener">${t}</a>`);
}

export function renderMarkdown(md: string): string {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];
  let i = 0;
  let inList = false;
  let listTag = "ul";

  const closeList = () => {
    if (inList) { out.push(`</${listTag}>`); inList = false; }
  };

  while (i < lines.length) {
    const line = lines[i];

    // fenced code block
    if (/^```/.test(line)) {
      closeList();
      const buf: string[] = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
      i++; // skip closing fence
      out.push(`<pre><code>${esc(buf.join("\n"))}</code></pre>`);
      continue;
    }

    // table: header row + separator row
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1])) {
      closeList();
      const cells = (r: string) => r.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
      const head = cells(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) { rows.push(cells(lines[i])); i++; }
      out.push("<table><thead><tr>" + head.map((h) => `<th>${inline(h)}</th>`).join("") + "</tr></thead><tbody>" +
        rows.map((r) => "<tr>" + r.map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>").join("") +
        "</tbody></table>");
      continue;
    }

    // headings
    const h = /^(#{1,6})\s+(.*)$/.exec(line);
    if (h) { closeList(); out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); i++; continue; }

    // hr
    if (/^\s*---\s*$/.test(line)) { closeList(); out.push("<hr/>"); i++; continue; }

    // blockquote
    if (/^\s*>\s?/.test(line)) { closeList(); out.push(`<blockquote>${inline(line.replace(/^\s*>\s?/, ""))}</blockquote>`); i++; continue; }

    // list items (ordered or unordered)
    const li = /^\s*([-*]|\d+\.)\s+(.*)$/.exec(line);
    if (li) {
      const wantTag = /\d+\./.test(li[1]) ? "ol" : "ul";
      if (!inList || listTag !== wantTag) { closeList(); listTag = wantTag; out.push(`<${listTag}>`); inList = true; }
      out.push(`<li>${inline(li[2])}</li>`);
      i++; continue;
    }

    // blank line
    if (/^\s*$/.test(line)) { closeList(); i++; continue; }

    // image-only line -> gallery (one or more images, no other text)
    if (/^(?:\s*!\[[^\]]*\]\([^)]+\)\s*)+$/.test(line)) {
      closeList();
      out.push(`<div class="gallery">${inline(line.trim())}</div>`);
      i++; continue;
    }

    // paragraph
    closeList();
    out.push(`<p>${inline(line)}</p>`);
    i++;
  }
  closeList();
  return out.join("\n");
}
