#!/usr/bin/env python3
"""add_floor_search.py (FLOOR-SEARCH v1) -- a search kit specific to each Datafort floor.

python3 add_floor_search.py ~/projects/payload KIT_DIR [--check]

Patches, with a .pre-floor-search backup of each file, and refuses to run twice:
  src/collections/entriesSearch.ts   NEW  GET /api/entries/search (hits + snippets, owner-only)
  src/collections/Entries.ts         registers the endpoint
  public/index.html                  per-floor search bar (scope, match mode, order, floor filters,
                                     canon day range), hit counts and snippets in the index,
                                     click a snippet to jump to that hit
  tools/packet-to-bundle.py          files the text of .md/.txt sources (Sourcebooks, DLCs) found in
                                     $DATAFORT_SOURCES (colon-separated dirs; default ~/Downloads/sources)
Every edit asserts its anchor; nothing is written unless every anchor matches.
"""
import pathlib, re, shutil, sys

MARK = "FLOOR-SEARCH v1"

def die(m): print("[FAIL]", m); sys.exit(1)

def one(t, pat, rep, name, flags=re.S):
    n, c = re.subn(pat, rep, t, count=1, flags=flags)
    if c != 1 or len(re.findall(pat, t, flags)) != 1:
        die(f"{name}: anchor matched {len(re.findall(pat, t, flags))} times: /{pat[:80]}/")
    return n

def lit(s): return re.escape(s)

def main():
    root = pathlib.Path(sys.argv[1]).expanduser().resolve(); kit = pathlib.Path(sys.argv[2]).expanduser().resolve()
    check = "--check" in sys.argv
    K = {n: (kit / n).read_text(encoding="utf-8") for n in ("entriesSearch.ts", "fs_config.js", "fs_search.js", "fs_loadtext.js", "fs_events.js", "fs.css")}
    ix_p, en_p, pb_p = root / "public/index.html", root / "src/collections/Entries.ts", root / "tools/packet-to-bundle.py"
    ix, en, pb = (p.read_text(encoding="utf-8") for p in (ix_p, en_p, pb_p))
    if MARK in ix or "entriesSearch" in en or "DATAFORT_SOURCES" in pb:
        die("already applied (restore the .pre-floor-search copies to re-run)")
    rep = lambda s: (lambda m: s)  # literal replacement (no backslash processing)

    # ---------------- index.html
    ix = one(ix, r"(</style>)(?![\s\S]*</style>)", rep(K["fs.css"] + "\n</style>"), "css")
    fbi = ix.index('<div class="floor-body" id="floor-body">'); hi = ix.rindex('</header>', 0, fbi); ls = ix.rindex("\n", 0, hi) + 1
    ix = ix[:ls] + ix[ls:hi] + '  <div class="findbar" id="findbar" hidden></div>\n' + ix[ls:]  # findbar: last row of the floor header
    ix = one(ix, r"(const FL = Object\.fromEntries\(FLOORS\.map\([^\n]*\n)", lambda m: m.group(1) + K["fs_config.js"], "FIND config")
    ix = one(ix, r"/\* full-text search: Postgres ILIKE.*?(?=function thumbHTML\()", rep(K["fs_search.js"]), "search + roster")
    ix = one(ix, r"async function loadText\(f, r\) \{.*?(?=/\* -{5,} detail: edit -{5,} \*/)", rep(K["fs_loadtext.js"]), "loadText")
    ix = one(ix, lit('terms: () => S.q.trim().toLowerCase().split(/\\s+/).filter(w => w.length > 1)'), rep("terms: () => qTerms()"), "sheet terms")
    ix = one(ix, lit('$("#search").parentElement.hidden = n === 0;'), rep('$("#search").parentElement.hidden = n === 0;\n    renderFind();'), "renderHead")
    ix = one(ix, lit('$("#search").addEventListener("input", e => { S.q = e.target.value; renderRoster(); ftSearch(); });') + r"\n",
             rep(K["fs_events.js"]), "search events")
    ix = one(ix, lit('S.editing = null; S.sel[S.floor] = b.dataset.id; S.view = "detail";'),
             rep('S.editing = null; S.sel[S.floor] = b.dataset.id; S.view = "detail"; S.jump = b.dataset.at ? { id: b.dataset.id, at: +b.dataset.at } : null;'), "roster click")
    ix = ix.replace("<script>\n(function () {", f"<script>\n/* {MARK} */\n(function () {{", 1) if "<script>\n(function () {" in ix else ix.replace("</head>", f"<!-- {MARK} -->\n</head>", 1)
    if MARK not in ix: die("marker")

    # ---------------- Entries.ts
    en = one(en, lit("import { snapshotSheet } from './SheetHistory'"), rep("import { snapshotSheet } from './SheetHistory'\nimport { entriesSearch } from './entriesSearch'"), "import")
    en = one(en, lit("hooks: { beforeChange: [stampOwner], afterChange: [snapshotSheet] },"),
             rep("hooks: { beforeChange: [stampOwner], afterChange: [snapshotSheet] },\n  // FLOOR-SEARCH v1: GET /api/entries/search?floor=&q=&mode=all|phrase\n  endpoints: [{ path: '/search', method: 'get', handler: entriesSearch }],"), "endpoint")

    # ---------------- packet-to-bundle.py
    pb = one(pb, r"^import json, pathlib, re, shutil, sys, unicodedata$", rep("import json, os, pathlib, re, shutil, sys, unicodedata"), "pb import", re.M)
    m = re.search(r"^([ \t]*)def with_text\(src, item\):\n(?:\1[ \t]+[^\n]*\n)+", pb, re.M)
    if not m: die("pb with_text")
    ind = m.group(1)
    add = (f"{ind}# {MARK}: the text of a .md/.txt source (Sourcebooks, DLCs), if a copy is on this machine\n"
           f"{ind}src_dirs = [pathlib.Path(d).expanduser() for d in os.environ.get('DATAFORT_SOURCES', '~/Downloads/sources').split(':') if d]\n"
           f"{ind}def add_src(fn, item):\n"
           f"{ind}    if fn.lower().endswith(('.md', '.txt')):\n"
           f"{ind}        for d in src_dirs:\n"
           f"{ind}            hits = sorted(d.rglob(fn)) if d.is_dir() else []\n"
           f"{ind}            if hits:\n"
           f"{ind}                return items.append(with_text(hits[0], item))\n"
           f"{ind}    items.append(item)\n\n")
    pb = pb[:m.end()] + "\n" + add + pb[m.end():].lstrip("\n")
    pb = one(pb, lit('items.append({"floor": "sourcebooks", "data": {"title": title,'), rep('add_src(fn, {"floor": "sourcebooks", "data": {"title": title,'), "pb sourcebooks")
    pb = one(pb, lit('items.append({"floor": "dlc", "data": {"title": title,'), rep('add_src(fn, {"floor": "dlc", "data": {"title": title,'), "pb dlc")

    if check: print("[OK] every anchor matched; --check: nothing written"); return
    for p in (ix_p, en_p, pb_p):
        b = p.with_name(p.name + ".pre-floor-search")
        if not b.exists(): shutil.copy2(p, b)
    ix_p.write_text(ix, encoding="utf-8"); en_p.write_text(en, encoding="utf-8"); pb_p.write_text(pb, encoding="utf-8")
    (root / "src/collections/entriesSearch.ts").write_text(K["entriesSearch.ts"], encoding="utf-8")
    print("[OK] patched index.html, Entries.ts, packet-to-bundle.py; wrote entriesSearch.ts")

if __name__ == "__main__":
    main()
