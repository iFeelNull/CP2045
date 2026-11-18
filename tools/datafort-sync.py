#!/usr/bin/env python3
"""
datafort-sync.py v1.1 -- file a play day's entries, canon and files into the local Datafort.

    python3 tools/datafort-sync.py BUNDLE_DIR            # dry run: prints the plan, changes nothing
    python3 tools/datafort-sync.py BUNDLE_DIR --apply    # pg_dump backup, then create/update/upload

BUNDLE_DIR/bundle.json:
    {
      "day": 112,
      "entries": [
        { "floor": "canon", "data": { "title": "...", "kind": "Event", "day": "112", "body": "..." },
          "files": { "file": "handouts/brief.pdf" } },
        { "floor": "npc", "data": { "handle": "Aster Vale", "disposition": "Wary" },
          "files": { "portrait": "portraits/aster.png" } },
        { "floor": "meta", "data": { "session": "112" } }
      ]
    }

  floor   pc | npc | sheets | sourcebooks | dlc | canon | meta
  match   field that identifies an existing entry on that floor (default: handle for pc/npc,
          title otherwise; meta has a single entry). Same value, case-insensitive = update.
  mode    "merge" (default: only the given fields change) or "replace" (data is exactly what's given)
  files   field -> path inside BUNDLE_DIR. Image fields (portrait, image, cover) go to
          datafort-images (PNG/JPEG/GIF/WebP <= 10 MB); "file" goes to datafort-files (PDF/EPUB).
  text    path inside BUNDLE_DIR to a UTF-8 text file (a day file, a full sheet): stored in the
          entry's server-side full text (needs tools/add_fulltext.py), shown on demand, searchable.
          Skipped when unchanged (sha256 kept in data.textSrc).

Auth: Payload API key of the Datafort's owner, read from ~/.config/datafort/api-key (mode 600)
or $DATAFORT_API_KEY. Sent as "Authorization: users API-Key <key>". Never printed.
Python stdlib only. Talks to http://localhost:8087 unless --base is given.
"""
import argparse, hashlib, json, mimetypes, os, pathlib, subprocess, sys, time, urllib.error, urllib.request, uuid

FLOORS = {"pc": "handle", "npc": "handle", "sheets": "title", "sourcebooks": "title",
          "dlc": "title", "canon": "title", "meta": None}
IMAGE_FIELDS = {"portrait", "image", "cover"}
FILE_FIELDS = {"file"}
NOW_MS = int(time.time() * 1000)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def die(msg):
    print(f"[FAIL] {msg}", file=sys.stderr); sys.exit(1)


class Api:
    def __init__(self, base, key):
        self.base, self.auth = base.rstrip("/"), f"users API-Key {key}"

    def call(self, method, path, body=None, form=None):
        headers = {"Authorization": self.auth, "Accept": "application/json"}
        data = None
        if form is not None:
            data, ctype = form
            headers["Content-Type"] = ctype
        elif body is not None:
            data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                j = json.loads(e.read()); err = j["errors"][0]
                detail = (err.get("data") or {}).get("errors", [{}])[0].get("message") or err.get("message")
            except Exception:
                detail = e.reason
            raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"cannot reach {self.base}: {e.reason} (is webstack-payload running?)") from None

    def upload(self, collection, path):
        boundary = "----datafort" + uuid.uuid4().hex
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix.lower() == ".epub":
            mime = "application/epub+zip"
        parts = [
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            f"Content-Type: {mime}\r\n\r\n".encode() + path.read_bytes() + b"\r\n",
            f'--{boundary}\r\nContent-Disposition: form-data; name="_payload"\r\n\r\n{{}}\r\n'.encode(),
            f"--{boundary}--\r\n".encode(),
        ]
        doc = self.call("POST", f"/api/{collection}?depth=0",
                        form=(b"".join(parts), f"multipart/form-data; boundary={boundary}"))["doc"]
        return f"pl:{collection}/{doc['id']}/{doc['filename']}", doc

    def drop_ref(self, ref):
        try:
            col, rid = ref[3:].split("/", 2)[:2]
            self.call("DELETE", f"/api/{col}/{rid}")
        except Exception as e:
            print(f"  [NOTE] could not delete replaced upload {ref}: {e}")


def norm(v):
    return str(v or "").strip().lower()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bundle")
    ap.add_argument("--apply", action="store_true", help="make the changes (default: dry run)")
    ap.add_argument("--base", default=os.environ.get("DATAFORT_BASE", "http://localhost:8087"))
    ap.add_argument("--key-file", default=os.path.expanduser("~/.config/datafort/api-key"))
    ap.add_argument("--no-backup", action="store_true", help="skip the pg_dump before --apply")
    ap.add_argument("--verbose", action="store_true", help="list every item in the plan")
    a = ap.parse_args()

    root = pathlib.Path(a.bundle)
    try:
        bundle = json.loads((root / "bundle.json").read_text(encoding="utf-8"))
    except Exception as e:
        die(f"cannot read {root/'bundle.json'}: {e}")
    key = os.environ.get("DATAFORT_API_KEY")
    if not key:
        kf = pathlib.Path(a.key_file)
        if not kf.is_file():
            die(f"no API key: {kf} missing (see the runbook, 'One-time setup')")
        if kf.stat().st_mode & 0o077:
            die(f"{kf} is readable by others; run: chmod 600 {kf}")
        key = kf.read_text().strip()
    api = Api(a.base, key)

    # ---- validate the bundle before touching anything
    items = bundle.get("entries") or []
    if not isinstance(items, list) or not items:
        die("bundle.json has no entries")
    for i, it in enumerate(items, 1):
        fl = it.get("floor")
        if fl not in FLOORS:
            die(f"entry {i}: floor {fl!r} is not one of {', '.join(FLOORS)}")
        if not isinstance(it.get("data"), dict):
            die(f"entry {i}: data must be an object")
        m = it.get("match", FLOORS[fl])
        if m and not str(it["data"].get(m, "")).strip():
            die(f"entry {i} ({fl}): match field {m!r} is empty")
        if it.get("mode", "merge") not in ("merge", "replace"):
            die(f"entry {i}: mode must be merge or replace")
        for field, rel in (it.get("files") or {}).items():
            p = root / rel
            if field not in IMAGE_FIELDS | FILE_FIELDS:
                die(f"entry {i}: files field {field!r} must be one of {sorted(IMAGE_FIELDS | FILE_FIELDS)}")
            if not p.is_file():
                die(f"entry {i}: file not found: {p}")
            if field in IMAGE_FIELDS and p.stat().st_size > 10 * 1024 * 1024:
                die(f"entry {i}: image over 10 MB: {p}")
        if it.get("text"):
            p = root / it["text"]
            if not p.is_file():
                die(f"entry {i}: text file not found: {p}")
            if len(p.read_text(encoding="utf-8")) > 5_000_000:
                die(f"entry {i}: text over 5,000,000 characters: {p}")

    # ---- current state (owner-only: the key's user sees exactly their Datafort)
    try:
        me = api.call("GET", "/api/users/me").get("user")
    except RuntimeError as e:
        die(str(e))
    if not me:
        die("the API key was not accepted (re-check ~/.config/datafort/api-key, and 'Enable API Key' on the user)")
    docs = api.call("GET", "/api/entries?pagination=false&depth=0&select[text]=false")["docs"]
    print(f"Datafort at {a.base} as {me.get('email')}: {len(docs)} entries on file. Bundle: day {bundle.get('day', '?')}, {len(items)} items.")

    # ---- plan
    plan = []
    for it in items:
        fl, mode = it["floor"], it.get("mode", "merge")
        m = it.get("match", FLOORS[fl])
        same = [d for d in docs if d["floor"] == fl and (m is None or norm(d["data"].get(m)) == norm(it["data"][m]))]
        if len(same) > 1:
            die(f"{fl} '{it['data'].get(m)}' matches {len(same)} existing entries; tidy duplicates in /admin first")
        cur = same[0] if same else None
        label = f"{fl}:{it['data'].get(m) if m else 'campaign'}"
        # upload only files whose content differs from what the entry already holds (<field>Src = sha256)
        it["_up"] = {f: rel for f, rel in (it.get("files") or {}).items()
                     if not cur or cur["data"].get(f + "Src") != sha(root / rel) or not cur["data"].get(f)}
        it["_text"] = bool(it.get("text")) and (not cur or cur["data"].get("textSrc") != sha(root / it["text"]))
        if cur:
            base = dict(cur["data"]) if mode == "merge" else {k: cur["data"][k] for k in ("seq", "createdAt") if k in cur["data"]}
            new = {**base, **it["data"]}
            changed = sorted(k for k in set(new) | set(cur["data"]) if new.get(k) != cur["data"].get(k) and k != "updatedAt")
            action = "UPDATE" if changed or it["_up"] or it["_text"] else "SAME"
            plan.append((action, label, it, cur, new, changed))
        else:
            seq = max([d["data"].get("seq") or 0 for d in docs if d["floor"] == fl] + [0]) + 1
            new = {**it["data"]}
            if fl != "meta":
                new.setdefault("seq", seq); new.setdefault("createdAt", NOW_MS)
            plan.append(("CREATE", label, it, None, new, sorted(new)))
            if fl != "meta":
                docs.append({"floor": fl, "data": {"seq": seq}})   # so two creates on one floor get distinct seq
    counts = {}
    for action, label, it, cur, new, changed in plan:
        counts.setdefault(it["floor"], {}).setdefault(action, 0)
        counts[it["floor"]][action] += 1
    for fl, c in counts.items():
        print(f"  {fl:12} " + "  ".join(f"{a} {n}" for a, n in sorted(c.items())))
    shown = 0
    for action, label, it, cur, new, changed in plan:
        if action == "SAME" and not a.verbose:
            continue
        if shown >= 40 and not a.verbose:
            print(f"  ... {sum(1 for p in plan if p[0] != 'SAME') - shown} more (use --verbose)"); break
        files = ", ".join(f"{k}<-{v}" for k, v in it["_up"].items())
        print(f"  {action:6} {label}" + (f"  fields: {', '.join(changed[:8])}{' …' if len(changed) > 8 else ''}" if changed and action == "UPDATE" else "")
              + (f"  files: {files}" if files else "") + ("  text" if it["_text"] else ""))
        shown += 1
    if not a.apply:
        print("\nDry run. Nothing changed. Re-run with --apply to file it."); return

    # ---- backup, then apply
    if not a.no_backup:
        out = pathlib.Path.home() / "backups" / f"payload-db-pre-sync-day{bundle.get('day', 'x')}-{time.strftime('%Y%m%d-%H%M%S')}.dump"
        out.parent.mkdir(mode=0o700, exist_ok=True)
        try:
            with open(out, "wb") as fh:
                r = subprocess.run(["podman", "exec", os.environ.get("DATAFORT_DB", "ws-payload-db"), "pg_dump", "-U", "payload", "-Fc", "payload"], stdout=fh)
        except FileNotFoundError:
            r = None
        if r is None or r.returncode != 0:
            out.unlink(missing_ok=True); die("pg_dump failed; not applying (use --no-backup to override)")
        out.chmod(0o600); print(f"[OK] backup {out}")
    done = 0
    for action, label, it, cur, new, changed in plan:
        if action == "SAME":
            continue
        replaced = []
        for field, rel in it["_up"].items():
            p = root / rel
            ref, doc = api.upload("datafort-images" if field in IMAGE_FIELDS else "datafort-files", p)
            old = (cur or {}).get("data", {}).get(field)
            if isinstance(old, str) and old.startswith("pl:") and old != ref:
                replaced.append(old)
            new[field], new[field + "Src"] = ref, sha(p)
            if field in FILE_FIELDS:
                new[field + "Name"], new[field + "Size"] = doc["filename"], doc.get("filesize") or p.stat().st_size
        if it["floor"] != "meta":
            new["updatedAt"] = NOW_MS
        body = {"data": new}
        if it["_text"]:
            tp = root / it["text"]
            body["text"], new["textSrc"] = tp.read_text(encoding="utf-8"), sha(tp)
        if cur:
            api.call("PATCH", f"/api/entries/{cur['id']}?depth=0&select[text]=false", body)
        else:
            api.call("POST", "/api/entries?depth=0&select[text]=false", {"floor": it["floor"], **body})
        for ref in replaced:
            api.drop_ref(ref)
        done += 1
        if a.verbose or done % 50 == 0 or done == sum(1 for p in plan if p[0] != "SAME"):
            print(f"[OK] {done} filed (last: {action.lower()}d {label})")
    print(f"\nFiled {done} item(s). Reload http://localhost:8087/ to see them.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        die(str(e))
