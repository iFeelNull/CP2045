#!/usr/bin/env python3
"""add_pdf_view.py (PDF-VIEW v1) -- entries with a PDF attached show the PDF itself under their details.

python3 add_pdf_view.py ~/projects/payload [--check]

  public/index.html                 detail pane: details on top, the PDF embedded below (browser viewer;
                                    Ctrl+F inside searches it); a search hit opens the PDF at its page;
                                    entries without a PDF keep the full-text view
  src/collections/entriesSearch.ts  each snippet carries `page`: the nearest PDF page marker above it
Needs FLOOR-SEARCH v1. Refuses to run twice; keeps .pre-pdf-view copies.
"""
import pathlib, re, shutil, sys

MARK = "PDF-VIEW v1"
def die(m): print("[FAIL]", m); sys.exit(1)
def one(t, pat, rep, name, flags=re.S):
    c = len(re.findall(pat, t, flags))
    if c != 1: die(f"{name}: anchor matched {c} times")
    return re.sub(pat, lambda m: rep, t, count=1, flags=flags)
lit = re.escape

RENDER = r'''/* PDF-VIEW v1: an entry with a PDF shows the PDF itself under its details */
function pdfOf(r) {
  const p = refParse(r.file);
  return p && p.col === FILES && /\.pdf$/i.test(r.fileName || p.name) ? refUrl(r.file) : "";
}
function pdfHTML(r, url, page) {
  const q = qTerms().join(" "), name = r.fileName || (refParse(r.file) || {}).name || "PDF";
  const hash = "#" + [page ? "page=" + page : "", "view=FitH", q ? "search=" + encodeURIComponent(q) : ""].filter(Boolean).join("&");
  return `<section class="d-pdf"><div class="pdf-bar"><p class="eyebrow">PDF · ${esc(name)}${r.fileSize ? " · " + fmtSize(r.fileSize) : ""}${page ? " · opened at page " + page : ""}</p>` +
    `<span class="pdf-acts"><a class="btn ghost sm" href="${esc(url + hash)}" target="_blank" rel="noopener noreferrer">Open in tab &#x2197;</a><a class="btn ghost sm" href="${esc(url)}" download="${esc(name)}">Download</a></span></div>` +
    `<p class="pdf-tip">To search inside the book: click the PDF, then Ctrl+F.${q ? " Search hits above open it at their page." : ""}</p>` +
    `<iframe class="pdf-frame" src="${esc(url + hash)}" title="${esc(name)}"></iframe></section>`;
}
function renderDetail() {
  const f = cur(), r = S.data[f.key].find(x => x.id === S.sel[f.key]);
  const d = $("#detail");
  if (!r) { d.innerHTML = ""; return; }
  const sheet = isSheet(f, r), pdf = sheet ? "" : pdfOf(r);
  let page = 0;
  if (pdf) {
    if (S.jump && S.jump.id === r.id && +S.jump.page) page = +S.jump.page;
    else if (S.q.trim() && FT.floor === f.key && FT.key === ftKey()) { const h = FT.res.get(r.id), s0 = h && h.snips && h.snips[0]; if (s0 && +s0.page) page = +s0.page; }
    S.jump = null;
  }
  d.innerHTML = barHTML(f, r, false) + `<article class="d-body">${READ[f.key](f, r)}` +
    (sheet ? `<section class="rs-host"></section>` : pdf ? pdfHTML(r, pdf, page) : r._tl ? `<section class="d-text"><p class="eyebrow">Full text · loading…</p></section>` : "") + `</article>`;
  if (pdf) d.querySelectorAll(".d-body > .book-file").forEach(e => e.remove());
  d.scrollTop = 0;
  if (sheet) mountSheet(r); else if (!pdf && r._tl) loadText(f, r);
}

'''
CSS = r'''/* PDF-VIEW v1 */
.d-pdf { margin-top: 18px; }
.pdf-bar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 16px; }
.pdf-bar .eyebrow { margin: 0; }
.pdf-acts { display: flex; gap: 8px; }
.pdf-tip { margin: 6px 0 10px; font-size: .78rem; color: var(--dim); }
.pdf-frame { display: block; width: 100%; height: max(78vh, 560px); border: 1px solid var(--line); background: #2a2a2e; }
'''
CTX_OLD = "      return { at: i, s: t.slice(a, b).replace(/\\s+/g, ' ').trim(), ctx: context(t, i) }"
CTX_NEW = "      return { at: i, s: t.slice(a, b).replace(/\\s+/g, ' ').trim(), ctx: context(t, i), page: pageAt(t, i) }"
PAGE_FN = r'''
/** PDF-VIEW v1: the nearest PDF page marker above a hit ('## PDF Page N', '<!-- PDF page N -->', 'PDF p.N'); 0 if none. */
const PAGE_RE = /(?:^#{1,6}\s*PDF\s*Page\s*(\d+)|<!--\s*PDF\s*page\s*(\d+)\s*-->|PDF\s*p\.\s*(\d+))/gim
function pageAt(text: string, at: number): number {
  const s = text.slice(Math.max(0, at - 400000), at)
  let n = 0, m: RegExpExecArray | null
  PAGE_RE.lastIndex = 0
  while ((m = PAGE_RE.exec(s))) n = Number(m[1] || m[2] || m[3]) || n
  return n
}
'''

def main():
    root = pathlib.Path(sys.argv[1]).expanduser().resolve(); check = "--check" in sys.argv
    ix_p, es_p = root / "public/index.html", root / "src/collections/entriesSearch.ts"
    ix, es = ix_p.read_text(encoding="utf-8"), es_p.read_text(encoding="utf-8")
    if MARK in ix or "pageAt" in es: die("already applied (restore the .pre-pdf-view copies to re-run)")
    if "FLOOR-SEARCH v1" not in ix: die("needs FLOOR-SEARCH v1 first")
    ix = one(ix, r"function renderDetail\(\) \{.*?(?=/\* RED-SHEET v1\.4)", RENDER, "renderDetail")
    ix = one(ix, lit('S.jump = b.dataset.at ? { id: b.dataset.id, at: +b.dataset.at } : null;'),
             'S.jump = b.dataset.at ? { id: b.dataset.id, at: +b.dataset.at, page: +b.dataset.page || 0 } : null;', "roster click")
    ix = one(ix, lit('data-at="${+sn.at || 0}">${has(sn.ctx) ? `<b>${esc(sn.ctx)}</b>` : ""}'),
             'data-at="${+sn.at || 0}" data-page="${+sn.page || 0}">${has(sn.ctx) || +sn.page ? `<b>${esc([sn.ctx, +sn.page && !/PDF\\s*(page|p\\.)\\s*\\d/i.test(sn.ctx || "") ? "PDF page " + sn.page : ""].filter(Boolean).join(" · "))}</b>` : ""}',
             "snippet page")
    ix = one(ix, r"(?=/\* FLOOR-SEARCH v1 \*/\n\.findbar \{)", CSS, "css")
    if MARK not in ix: die("marker")
    es = one(es, lit(CTX_OLD), CTX_NEW, "snippet page field")
    es = one(es, lit("export const entriesSearch"), PAGE_FN.lstrip("\n") + "\nexport const entriesSearch", "pageAt fn")
    if check: print("[OK] every anchor matched; --check: nothing written"); return
    for p in (ix_p, es_p):
        b = p.with_name(p.name + ".pre-pdf-view")
        if not b.exists(): shutil.copy2(p, b)
    ix_p.write_text(ix, encoding="utf-8"); es_p.write_text(es, encoding="utf-8")
    print("[OK] patched index.html and entriesSearch.ts")

if __name__ == "__main__":
    main()
