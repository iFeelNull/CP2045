#!/usr/bin/env python3
"""
add_sheet_view.py v1.4 -- the RED character sheet on F01/F02, sheet history, and F02 = sheet NPCs only.

    python3 tools/add_sheet_view.py PROJECT_DIR      # e.g. ~/projects/payload (run from the unzipped kit)

What it does (each step is skipped if already done, so it is safe to re-run):
  public/sheet.js, public/sheet.css      the RED 3-page sheet renderer (copied from this kit)
  public/index.html                      PCs/NPCs that carry a sheet open as the RED sheet with
                                         page tabs, a version picker and "changes since" marks
  src/collections/SheetHistory.ts        new collection: one row per version of a PC/NPC sheet
  src/collections/Entries.ts             afterChange hook that saves the version
  src/payload.config.ts                  registers the collection (Postgres table made on restart)
  tools/packet-to-bundle.py              NPC floor = only NPCs with their own npc-<name>.md;
                                         every PC/NPC item carries asOfDay (the day it was filed for)
  tools/datafort-sync.py                 --prune npc: delete NPC entries the bundle no longer lists
Restart the stack afterwards (the collection and the hook load at start).
"""
import pathlib, re, shutil, subprocess, sys

KIT = pathlib.Path(__file__).resolve().parent.parent
MARK = "RED-SHEET v1.4"

def die(m):
    print(f"[FAIL] {m}", file=sys.stderr); sys.exit(1)

def edit(path, steps):
    """steps: (name, done_test(text)->bool, fn(text)->text). Asserts each change lands exactly once."""
    t = path.read_text(encoding="utf-8"); orig = t
    for name, done, fn in steps:
        if done(t):
            print(f"  [SKIP] {path.name}: {name} (already done)"); continue
        n = fn(t)
        if n == t: die(f"{path.name}: {name}: anchor not found; nothing written")
        t = n; print(f"  [OK]   {path.name}: {name}")
    if t != orig:
        path.write_text(t, encoding="utf-8")

def once(t, old, new):
    c = t.count(old)
    if c != 1: die(f"expected 1 match, found {c}: {old[:70]!r}")
    return t.replace(old, new)

def resub(t, pat, rep, flags=0):
    n, c = re.subn(pat, rep, t, count=0, flags=flags)
    if c != 1: die(f"expected 1 match, found {c}: /{pat[:70]}/")
    return n

def main():
    if len(sys.argv) != 2: die(__doc__)
    P = pathlib.Path(sys.argv[1]).expanduser().resolve()
    for need in ("public/index.html", "src/collections/Entries.ts", "src/payload.config.ts", "tools/packet-to-bundle.py", "tools/datafort-sync.py"):
        if not (P / need).is_file(): die(f"{P / need} not found (is this the Payload project?)")

    # ---- new files
    for rel in ("public/sheet.js", "public/sheet.css", "src/collections/SheetHistory.ts"):
        src, dst = KIT / rel, P / rel
        if not src.is_file(): die(f"kit file missing: {src}")
        if dst.is_file() and dst.read_bytes() == src.read_bytes():
            print(f"  [SKIP] {rel} (same)"); continue
        shutil.copyfile(src, dst); print(f"  [OK]   {rel}")

    # ---- page
    edit(P / "public/index.html", [
        ("sheet stylesheet", lambda t: 'href="sheet.css' in t,
         lambda t: once(t, "</style>", '</style>\n<link rel="stylesheet" href="sheet.css?v=14">')),
        ("sheet script", lambda t: 'src="sheet.js' in t,
         lambda t: once(t, '<script src="config.js"></script>', '<script src="config.js"></script>\n<script src="sheet.js?v=14"></script>')),
        ("PC read view -> RED sheet", lambda t: "/* RED sheet: pc */" in t,
         lambda t: resub(t, r"(\n[ \t]*pc\(f, r\) \{\n)", r"\1    if (r._tl && window.RedSheet) return headHTML(f, r, { sub: r.name }); /* RED sheet: pc */\n")),
        ("NPC read view -> RED sheet", lambda t: "/* RED sheet: npc */" in t,
         lambda t: resub(t, r"(\n[ \t]*npc\(f, r\) \{\n)", r"\1    if (r._tl && window.RedSheet) return headHTML(f, r, { sub: r.role, pills: [r.status] }); /* RED sheet: npc */\n")),
        ("detail pane mounts the sheet", lambda t: "rs-host" in t,
         lambda t: resub(once(t, "(r._tl ? `<section class=\"d-text\">", "(isSheet(f, r) ? `<section class=\"rs-host\"></section>` : r._tl ? `<section class=\"d-text\">"),
                         r"\n([ \t]*)if \(r\._tl\) loadText\(f, r\);\n", r"\n\1if (isSheet(f, r)) mountSheet(r); else if (r._tl) loadText(f, r);\n")),
        ("search re-highlights the sheet", lambda t: "isSheet(f, r) ? mountSheet(r) : loadText(f, r)" in t,
         lambda t: once(t, "if (r && r._tl && !S.editing) loadText(f, r);", "if (r && r._tl && !S.editing) (isSheet(f, r) ? mountSheet(r) : loadText(f, r));")),
        ("sheet helpers", lambda t: MARK in t,
         lambda t: once(t, "/* full text of one entry:", f"""/* {MARK}: PCs and NPCs with a sheet open as the official RED character sheet (public/sheet.js) */
function isSheet(f, r) {{ return (f.key === "pc" || f.key === "npc") && !!r._tl && !!window.RedSheet; }}
async function sheetText(id) {{
  let t = TEXT.get(id);
  if (t === undefined) {{
    t = (await API.http("GET", "/api/entries/" + encodeURIComponent(id) + "?depth=0&select[text]=true")).text || "";
    TEXT.set(id, t); if (TEXT.size > 12) TEXT.delete(TEXT.keys().next().value);
  }}
  return t;
}}
function mountSheet(r) {{
  const el = $("#detail .rs-host"); if (!el) return;
  window.RedSheet.mount(el, r, {{
    http: (m, u) => API.http(m, u), text: sheetText, markText, fmtSize,
    terms: () => S.q.trim().toLowerCase().split(/\\s+/).filter(w => w.length > 1)
  }}).catch(e => {{ el.innerHTML = `<p class="eyebrow">Sheet</p><p>${{esc(errMsg(e))}}</p>`; }});
}}

/* full text of one entry:""")),
    ])

    # ---- collections
    edit(P / "src/collections/Entries.ts", [
        ("import the snapshot hook", lambda t: "snapshotSheet" in t.split("export const")[0],
         lambda t: once(t, "import { ownerField, ownerOnly, signedIn, stampOwner } from './datafortAccess'",
                        "import { ownerField, ownerOnly, signedIn, stampOwner } from './datafortAccess'\nimport { snapshotSheet } from './SheetHistory'")),
        ("afterChange: save sheet versions", lambda t: "afterChange: [snapshotSheet]" in t,
         lambda t: once(t, "hooks: { beforeChange: [stampOwner] },", "hooks: { beforeChange: [stampOwner], afterChange: [snapshotSheet] },")),
    ])
    edit(P / "src/payload.config.ts", [
        ("import SheetHistory", lambda t: "from './collections/SheetHistory'" in t,
         lambda t: once(t, "import { Entries } from './collections/Entries'", "import { Entries } from './collections/Entries'\nimport { SheetHistory } from './collections/SheetHistory'")),
        ("register SheetHistory", lambda t: "SheetHistory]" in t or "SheetHistory," in t,
         lambda t: once(t, "collections: [Users, Media, Entries, DatafortImages, DatafortFiles],", "collections: [Users, Media, Entries, DatafortImages, DatafortFiles, SheetHistory],")),
    ])

    # ---- bundle builder: F02 = NPCs with their own sheet; asOfDay on PCs/NPCs
    edit(P / "tools/packet-to-bundle.py", [
        ("NPC floor: sheet NPCs only", lambda t: "# F02 lists only NPCs with their own" in t,
         lambda t: resub(t, r"(\n([ \t]+)if len\(hits\) == 1:\n([ \t]+)with_text\(sheets\[hits\[0\]\], item\); used\.add\(hits\[0\]\)\n)[ \t]+items\.append\(item\)\n",
                         lambda m: m.group(1) + m.group(3) + "items.append(item)  # F02 lists only NPCs with their own npc-<name>.md sheet (Day-121 rule)\n")),
        ("asOfDay on PC/NPC items", lambda t: "it['data']['asOfDay'] = last_day" in t,
         lambda t: resub(t, r"\n([ \t]*)titles = \{\}\n",
                         lambda m: f"\n{m.group(1)}for it in items:  # the play day each PC/NPC sheet was filed for (labels its sheet-history version)\n{m.group(1)}    if it['floor'] in ('pc', 'npc'):\n{m.group(1)}        it['data']['asOfDay'] = last_day\n{m.group(1)}titles = {{}}\n")),
        ("docstring", lambda t: True or "NPCs with their own npc-<name>.md sheet only" in t,
         lambda t: once(t, "NPCs one per row; npc-<name>.md sheet as full text", "NPCs with their own npc-<name>.md sheet only (row data from §A)")),
    ])

    # ---- sync: --prune FLOOR
    edit(P / "tools/datafort-sync.py", [
        ("--prune option", lambda t: '"--prune"' in t,
         lambda t: resub(t, r'\n([ \t]*)(ap\.add_argument\("--verbose"[^\n]*)\n',
                         lambda m: f'\n{m.group(1)}{m.group(2)}\n{m.group(1)}ap.add_argument("--prune", action="append", choices=["npc", "pc"], default=[],\n'
                                   f'{m.group(1)}                help="delete entries on this floor that the bundle does not list (F02: NPCs without an npc-<name>.md sheet)")\n')),
        ("prune plan", lambda t: "# ---- prune" in t,
         lambda t: resub(t, r"\n([ \t]*)counts = \{\}\n([ \t]*)for action, label, it, cur, new, changed in plan:\n",
                         lambda m: (f"\n{m.group(1)}# ---- prune: entries on --prune floors that no bundle item matched (backed up with the rest before --apply)\n"
                                    f"{m.group(1)}for fl in a.prune:\n"
                                    f"{m.group(1)}    if not any(it['floor'] == fl for it in items):\n"
                                    f"{m.group(1)}        die(f'--prune {{fl}}: the bundle has no {{fl}} items; refusing to empty the floor')\n"
                                    f"{m.group(1)}matched = {{p[3]['id'] for p in plan if p[3]}}\n"
                                    f"{m.group(1)}for d in list(docs):\n"
                                    f"{m.group(1)}    if d.get('id') is not None and d['floor'] in a.prune and d['id'] not in matched:\n"
                                    f"{m.group(1)}        plan.append(('DELETE', f\"{{d['floor']}}:{{d['data'].get(FLOORS[d['floor']] or 'title', '')}}\", {{'floor': d['floor'], '_up': {{}}, '_text': False}}, d, {{}}, []))\n"
                                    f"{m.group(1)}counts = {{}}\n{m.group(2)}for action, label, it, cur, new, changed in plan:\n"))),
        ("prune apply", lambda t: 'if action == "DELETE":' in t,
         lambda t: resub(t, r"\n([ \t]*)replaced = \[\]\n",
                         lambda m: f"\n{m.group(1)}if action == \"DELETE\":\n{m.group(1)}    api.call(\"DELETE\", f\"/api/entries/{{cur['id']}}\")\n{m.group(1)}    done += 1\n{m.group(1)}    continue\n{m.group(1)}replaced = []\n")),
    ])

    # ---- SELinux: new files must carry the project's label (never user_home_t from ~/Downloads)
    try:
        if subprocess.run(["selinuxenabled"]).returncode == 0:
            subprocess.run(["chcon", "-R", "--reference=" + str(P), str(P / "public"), str(P / "src"), str(P / "tools")], check=True)
            print("  [OK]   SELinux labels matched to the project")
    except FileNotFoundError:
        pass
    print(f"\nDone. Restart: systemctl --user restart webstack-payload.service")

if __name__ == "__main__":
    main()
