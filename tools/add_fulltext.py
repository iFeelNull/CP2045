"""Datafort: server-side full text for large entries (day files, full sheets, reference docs).

    python3 tools/add_fulltext.py <project-dir>      # then restart webstack-payload

What it adds (idempotent; prints "skip" for anything already there):
  Payload  Entries.text (long markdown, up to 5,000,000 chars) + Entries.textLength (auto)
  Page     list loads exclude text (select[text]=false), so 50 MB of canon never reaches the browser at once
           opening an entry with text fetches it on demand and shows it under "Full text", search terms highlighted
           search also asks Postgres (where[text][like]) on floors that have text; results merge with the normal search
           a form save MERGES into the stored data (it used to replace it, dropping fields the form doesn't show)
           export leaves out helper keys (_tl)
  Options  more Reference-sheet categories, canon kind "Day log", sourcebook format "Text"
Requires add_canon_floor.py to have run first.
"""
import pathlib
import sys

P = pathlib.Path(sys.argv[1])


def patch(path, old, new, marker, count=1):
    s = path.read_text(encoding="utf-8")
    if marker in s:
        print(f"skip  {path.name}: {marker[:50]!r}")
        return
    n = s.count(old)
    assert n == count, f"{path}: anchor found {n}x (want {count}): {old[:70]!r}"
    path.write_text(s.replace(old, new), encoding="utf-8")
    print(f"patch {path.name}: {marker[:50]}")


ENT = P / "src/collections/Entries.ts"
HTML = P / "public/index.html"
if "key: \"canon\"" not in HTML.read_text(encoding="utf-8"):
    sys.exit("run tools/add_canon_floor.py first")

# ---------------------------------------------------------------- Payload: text + textLength
patch(ENT, "    ownerField,\n  ],",
      """    {
      // Long markdown (day files, full sheets). Kept out of list loads (select[text]=false),
      // fetched when an entry is opened, searched server-side with where[text][like].
      name: 'text',
      type: 'textarea',
      maxLength: 5_000_000, // Payload's default cap is 40,000; day files run to ~330,000
      admin: { description: 'Full text (large). Loaded on demand by the Datafort page.' },
    },
    {
      name: 'textLength',
      type: 'number',
      admin: { readOnly: true, position: 'sidebar' },
      hooks: {
        beforeChange: [
          // recompute when text is sent; otherwise keep the stored length (a data-only PATCH must not clear it)
          ({ siblingData, originalDoc }) =>
            typeof siblingData?.text === 'string' ? siblingData.text.length : (originalDoc?.textLength ?? null),
        ],
      },
    },
    ownerField,
  ],""", "name: 'text',")

# ---------------------------------------------------------------- page: list load without text, remember which rows have it
patch(HTML, 'docs = (await this.http("GET", "/api/entries?pagination=false&depth=0&sort=createdAt")).docs || [];',
      'docs = (await this.http("GET", "/api/entries?pagination=false&depth=0&sort=createdAt&select[text]=false")).docs || [];',
      "sort=createdAt&select[text]=false")
patch(HTML, "if (by[row.floor]) by[row.floor].push(Object.assign({}, row.data, { id: String(row.id) }));",
      "if (by[row.floor]) by[row.floor].push(Object.assign({}, row.data, { id: String(row.id), _tl: row.textLength || 0 }));   // _tl: server-side text length",
      "_tl: row.textLength || 0")

# ---------------------------------------------------------------- page: form save merges into stored data
patch(HTML, """    async save(key, id, body) {
      const clean = Object.assign({}, body); delete clean.id;""",
      """    async save(key, id, body) {
      // Merge into what is stored: the form only carries its own fields; imported keys must survive an edit.
      const prev = id ? S.data[key].find(r => r.id === id) : null;
      const clean = Object.assign({}, prev || {}, body); delete clean.id;
      Object.keys(clean).forEach(k => { if (k[0] === "_") delete clean[k]; });""",
      "imported keys must survive an edit")
patch(HTML, """      const list = S.data[key].filter(r => r.id !== id);
      list.push(Object.assign({}, clean, { id }));
      S.data[key] = sorted(list);
      return id;""",
      """      const list = S.data[key].filter(r => r.id !== id);
      list.push(Object.assign({}, clean, { id, _tl: prev ? prev._tl : 0 }));
      S.data[key] = sorted(list);
      return id;""",
      "_tl: prev ? prev._tl : 0")
patch(HTML, "const c = Object.assign({}, r); delete c.id; return c; }));",
      "const c = Object.assign({}, r); delete c.id; Object.keys(c).forEach(k => { if (k[0] === \"_\") delete c[k]; }); return c; }));",
      'if (k[0] === "_") delete c[k]; }); return c; }));')

# ---------------------------------------------------------------- page: server-side search merged into matches()
patch(HTML, """  function matches(f, r, q) {
    if (!q) return true;""",
      """  /* full-text search: Postgres ILIKE over Entries.text for the current floor (words AND-ed by Payload's "like") */
  const FT = { floor: null, q: "", ids: new Set(), timer: 0, seq: 0 };
  function ftSearch() {
    clearTimeout(FT.timer);
    const f = cur(), q = S.q.trim();
    if (S.mode !== "net" || q.length < 3 || !S.data[f.key].some(r => r._tl)) { FT.floor = null; FT.q = ""; FT.ids = new Set(); return; }
    FT.timer = setTimeout(async () => {
      const my = ++FT.seq;
      try {
        const j = await API.http("GET", "/api/entries?pagination=false&depth=0&select[floor]=true&where[floor][equals]=" +
          encodeURIComponent(f.key) + "&where[text][like]=" + encodeURIComponent(q));
        if (my !== FT.seq) return;
        FT.floor = f.key; FT.q = q.toLowerCase(); FT.ids = new Set((j.docs || []).map(d => String(d.id)));
        renderRoster();
        const r = S.data[f.key].find(x => x.id === S.sel[f.key]);
        if (r && r._tl && !S.editing) loadText(f, r);
      } catch (e) { if (my === FT.seq) toast(errMsg(e), true); }
    }, 300);
  }
  function matches(f, r, q) {
    if (!q) return true;
    if (FT.floor === f.key && FT.q === q && FT.ids.has(r.id)) return true;""",
      "const FT = { floor: null")
patch(HTML, '$("#search").addEventListener("input", e => { S.q = e.target.value; renderRoster(); });',
      '$("#search").addEventListener("input", e => { S.q = e.target.value; renderRoster(); ftSearch(); });',
      "renderRoster(); ftSearch(); });")

# ---------------------------------------------------------------- page: full text in the detail pane, on demand
patch(HTML, """    d.innerHTML = barHTML(f, r, false) + `<article class="d-body">${READ[f.key](f, r)}</article>`;
    d.scrollTop = 0;
  }""",
      """    d.innerHTML = barHTML(f, r, false) + `<article class="d-body">${READ[f.key](f, r)}` +
      (r._tl ? `<section class="d-text"><p class="eyebrow">Full text · loading…</p></section>` : "") + `</article>`;
    d.scrollTop = 0;
    if (r._tl) loadText(f, r);
  }

  /* full text of one entry: fetched on demand, cached (last 12), search terms highlighted, first match scrolled into view */
  const TEXT = new Map();
  function markText(t, terms) {
    if (!terms.length) return [esc(t), 0];
    const re = new RegExp(terms.map(w => w.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&")).join("|"), "gi");
    let out = "", i = 0, n = 0, m;
    while ((m = re.exec(t))) {
      if (!m[0]) { re.lastIndex++; continue; }
      out += esc(t.slice(i, m.index)) + "<mark>" + esc(m[0]) + "</mark>"; i = m.index + m[0].length; n++;
    }
    return [out + esc(t.slice(i)), n];
  }
  async function loadText(f, r) {
    let t = TEXT.get(r.id);
    if (t === undefined) {
      try { t = (await API.http("GET", "/api/entries/" + encodeURIComponent(r.id) + "?depth=0&select[text]=true")).text || ""; }
      catch (e) { const b = $("#detail .d-text"); if (b) b.innerHTML = `<p class="eyebrow">Full text</p><p>${esc(errMsg(e))}</p>`; return; }
      TEXT.set(r.id, t); if (TEXT.size > 12) TEXT.delete(TEXT.keys().next().value);
    }
    const box = $("#detail .d-text");
    if (!box || S.sel[f.key] !== r.id) return;          // the reader moved on while it loaded
    const terms = S.q.trim().toLowerCase().split(/\\s+/).filter(w => w.length > 1);
    const [html, n] = markText(t, terms);
    box.innerHTML = `<p class="eyebrow">Full text · ${fmtSize(t.length)}${terms.length ? " · " + n + (n === 1 ? " match" : " matches") : ""}</p><pre class="fulltext">${html}</pre>`;
    const m = box.querySelector("mark"); if (m) m.scrollIntoView({ block: "center" });
  }""",
      "const TEXT = new Map();")
patch(HTML, "</style>",
      """/* full text (server-side, on demand) */
.d-text { margin-top: 28px; }
.d-text .eyebrow { margin-bottom: 10px; }
.fulltext { white-space: pre-wrap; word-break: break-word; margin: 0; padding: 14px 16px; font: 13px/1.55 var(--f-mono);
  color: var(--fg); background: var(--field); border: 1px solid var(--line); }
.fulltext mark { background: var(--accent-2); color: var(--on-accent); padding: 0 1px; }
</style>""", ".fulltext mark", count=1)

# ---------------------------------------------------------------- options used by imported campaign packets
patch(HTML, 'opts: ["Rules", "Table", "Map", "Handout", "House rule", "Session log", "Other"] },',
      'opts: ["Rules", "Table", "Map", "Handout", "House rule", "Session log", "Campaign state", "Character sheet", "Architecture", "Vehicle", "Arc", "Board", "Master list", "Financial", "Reference", "Other"] },',
      '"Campaign state", "Character sheet"')
patch(HTML, 'opts: ["Event", "Person", "Place", "Faction", "Item", "Ruling", "Lore", "Thread"] },',
      'opts: ["Day log", "Event", "Person", "Place", "Faction", "Item", "Ruling", "Lore", "Thread"] },',
      '["Day log", "Event"')
patch(HTML, 'opts: ["Print", "PDF", "Print + PDF"] },',
      'opts: ["Print", "PDF", "Print + PDF", "Text"] },',
      '"Print + PDF", "Text"]')
