#!/usr/bin/env python3
# FLOOR-SEARCH v1 smoke test: calls /api/entries/search with the sync tool's API key (never printed)
import json, os, pathlib, re, sys, time, urllib.parse, urllib.request
src = (pathlib.Path.home() / "projects/payload/tools/datafort-sync.py").read_text()
kf = pathlib.Path.home() / ".config/datafort/api-key"
key = os.environ.get("DATAFORT_API_KEY") or (kf.read_text().strip() if kf and kf.is_file() else "")
if not key: sys.exit("no key")
base = os.environ.get("DATAFORT_BASE", "http://localhost:8087")
def go(floor, q, mode="all"):
    u = base + "/api/entries/search?" + urllib.parse.urlencode({"floor": floor, "q": q, "mode": mode})
    r = urllib.request.Request(u, headers={"Authorization": "users API-Key " + key, "Accept": "application/json"})
    t0 = time.time()
    try:
        j = json.load(urllib.request.urlopen(r, timeout=60))
    except urllib.error.HTTPError as e:
        print(floor, q, "HTTP", e.code, e.read()[:200]); return
    docs = j.get("docs", [])
    print(f"== {floor} '{q}' ({mode}): {len(docs)} entries, {sum(d['hits'] for d in docs)} hits, {time.time()-t0:.2f}s")
    for d in sorted(docs, key=lambda d: -d["hits"])[:2]:
        for s in d["snips"][:2]:
            print(f"   id {d['id']} x{d['hits']} [{s['ctx']}] {s['s'][:110]}")
for a in sys.argv[1:]:
    f, q, *mo = a.split(":")
    go(f, q, *(mo or ["all"]))
