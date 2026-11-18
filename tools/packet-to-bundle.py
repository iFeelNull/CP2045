#!/usr/bin/env python3
"""
packet-to-bundle.py v1.0 -- turn a Slipstream (Cyberpunk RED 2045) packet into a Datafort bundle.

    python3 tools/packet-to-bundle.py PACKET_DIR OUT_DIR      # then: datafort-sync.py OUT_DIR

PACKET_DIR is an unzipped packet (<X>.zip from Drive zips/, flat, with canon/). OUT_DIR is created
fresh (it must not exist) with bundle.json and text/ (copies of the files whose full text is filed).

What goes where (one bundle item per entry; datafort-sync matches and only files what changed):
  canon/day-*.md (via canon-index FILE REGISTER)  -> Canon       "Day 120 · part 2", kind Day log, full text
  cp-ref-npc-master-list.md §A (NPCs in play)     -> NPCs        one per row; npc-<name>.md sheet as full text
  pc-*.md                                         -> PCs         the sheet as full text
  cp-ref-* · cp-arc-* · cp-homebrew-* · state ·   -> Reference   category by file kind, manifest description,
  kickoff · CHARACTER-SHEETS · deck sheet ·                      full text; matched on the file name (source)
  canon-index
  manifest §4 source layer: rules/ world/         -> Sourcebooks catalogue rows (the files live in Drive/Project)
                            dlc/ homebrew/        -> DLCs
  campaign name + last closed day                 -> meta
Never filed: gm-arc-* (sealed, GM-only), engine/, scripts/, proof files, name pools, the manifest,
the close prompt, the engine config.
Stdlib only.
"""
import json, os, pathlib, re, shutil, sys, unicodedata

SEALED = re.compile(r"^gm-arc-")
SKIP = {"cp-ref-manifest.md", "cp-day-close-prompt.md", "cp-engine-campaign.json",
        "CP_first_names.md", "CP_last_names.md", "CP_handles.md"}


def die(msg):
    print(f"[FAIL] {msg}", file=sys.stderr); sys.exit(1)


def slug(s):
    """'Iulia Yrkillsdóttir' -> 'iulia-yrkillsdottir' (accent-insensitive, matches npc-<slug>.md)"""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def plain(s):
    """markdown cell -> plain text (bold/italics/backticks/links/br removed)"""
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return re.sub(r"\*\*|__|`|(?<!\w)\*(?!\s)|(?<!\s)\*(?!\w)", "", s).strip()


def h1(path):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:40]:
        if line.startswith("# "):
            return plain(line[2:]).strip()
    return path.stem.replace("cp-ref-", "").replace("-", " ").upper()


def table_rows(lines):
    """yield cell lists for markdown table body rows (skips header + separator)"""
    for l in lines:
        if l.startswith("|") and not re.match(r"^\|\s*:?-{3}", l):
            yield [c.strip() for c in l.strip().strip("|").split("|")]


def section(lines, start_pat, end_pat):
    out, on = [], False
    for l in lines:
        if re.match(start_pat, l):
            on = True; continue
        if on and re.match(end_pat, l):
            break
        if on:
            out.append(l)
    return out


def main():
    if len(sys.argv) != 3:
        die("usage: packet-to-bundle.py PACKET_DIR OUT_DIR")
    pk, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    if not (pk / "canon-index.md").is_file() or not (pk / "canon").is_dir():
        die(f"{pk} is not an unzipped packet (no canon-index.md / canon/)")
    if out.exists():
        die(f"{out} exists; give a new folder")
    (out / "text").mkdir(parents=True)
    items = []

    def with_text(src, item):
        dst = out / "text" / src.name
        shutil.copyfile(src, dst)
        item["text"] = f"text/{src.name}"
        return item

    # FLOOR-SEARCH v1: the text of a .md/.txt source (Sourcebooks, DLCs), if a copy is on this machine
    src_dirs = [pathlib.Path(d).expanduser() for d in os.environ.get('DATAFORT_SOURCES', '~/Downloads/sources').split(':') if d]
    def add_src(fn, item):
        if fn.lower().endswith(('.md', '.txt')):
            for d in src_dirs:
                hits = sorted(d.rglob(fn)) if d.is_dir() else []
                if hits:
                    return items.append(with_text(hits[0], item))
        items.append(item)

    manifest = (pk / "cp-ref-manifest.md").read_text(encoding="utf-8") if (pk / "cp-ref-manifest.md").is_file() else ""
    mlines = manifest.splitlines()
    desc = {}
    for c in table_rows(mlines):
        m = re.match(r"^`([^`]+)`$", c[0]) if c else None
        if m and len(c) >= 2:
            desc.setdefault(m.group(1), plain(c[-1]))

    # ---------------------------------------------------------------- canon: one entry per day file (part)
    idx = (pk / "canon-index.md").read_text(encoding="utf-8").splitlines()
    reg = [c for c in table_rows(section(idx, r"^## FILE REGISTER", r"^## ")) if len(c) >= 4 and c[0] != "Day"]
    parts = {}
    for c in reg:
        parts[c[0]] = parts.get(c[0], 0) + 1
    last_day = 0
    for c in reg:
        day, part, date, fn = c[0], c[1], c[2], c[3].strip("`")
        f = pk / fn
        if not f.is_file():
            die(f"canon-index names {fn}, which is not in the packet")
        dnum = day.lstrip("0") or "0"
        nums = [int(x) for x in re.findall(r"\d+", day)]
        last_day = max([last_day] + nums)
        p = "" if part in ("—", "-", "") else part
        title = f"Day {dnum}" + (f" · part {p}" if p else "")
        items.append(with_text(f, {"floor": "canon", "data": {
            "title": title, "kind": "Day log", "status": "Canon", "day": dnum, "when": date,
            "summary": f"Play record of Day {dnum}" + (f", part {p} of {parts[day]}" if p else "") + f" — {date}. "
                       "The raw day export as filed at the rollover; open it to read or search the full text.",
            "source": fn}}))

    # ---------------------------------------------------------------- NPCs: master list §A + per-NPC sheets
    ml = pk / "cp-ref-npc-master-list.md"
    sheets = {p.stem[4:]: p for p in pk.glob("npc-*.md")}          # npc-heather-slipstream -> heather-slipstream
    used = set()
    if ml.is_file():
        rows = list(table_rows(section(ml.read_text(encoding="utf-8").splitlines(), r"^## A ", r"^## [B-Z] ")))
        head = rows[0] if rows and rows[0][0].lower().startswith("first") else None
        seen = set()
        for c in rows[1:] if head else rows:
            if len(c) < 16 or c[0].lower().startswith("first"):
                continue
            first, last = plain(c[0]), plain(c[1])
            handle = " ".join(x for x in (first, last) if x and x not in ("—", "-"))
            if not handle or slug(handle) in seen:
                continue
            seen.add(slug(handle))
            life = plain(c[2])
            role_full = plain(c[13])
            role = re.split(r"\s+·\s+|\n", role_full)[0][:140]
            look = " · ".join(f"{k}: {plain(v)}" for k, v in (("Sex", c[3]), ("Age", c[4]), ("Race", c[5]), ("Height", c[6]), ("Weight", c[7]),
                                                               ("Build", c[8]), ("Hair", c[9]), ("Eyes", c[10])) if plain(v) not in ("", "—", "-"))
            chrome = plain(c[12])
            notes = "\n".join(x for x in (
                f"{life}" + (f" · {look}" if look else ""),
                f"Chrome ({'visible' if plain(c[11]).upper() == 'Y' else 'not visible'}): {chrome}" if chrome not in ("", "—") else "",
                f"Appears on days: {plain(c[14])}" if plain(c[14]) not in ("", "—") else "",
                f"Voice and mannerisms: {plain(c[15])}" if plain(c[15]) not in ("", "—") else "",
                f"Where they sit: {role_full}" if len(role_full) > len(role) else "") if x)
            item = {"floor": "npc", "data": {
                "handle": handle, "name": handle, "role": role, "system": "RED",
                "status": "Active" if life.lower().startswith("living") else "Flatlined" if life.lower().startswith("deceased") else "Unknown",
                "notes": notes}}
            # a sheet belongs to this row when every word of its file name is in the row's name:
            # npc-jake-pulido.md -> 'Jacob "Jake" Pulido'; npc-iulia-yrkillsdottir.md -> 'Iulia Yrkillsdóttir'
            words = set(slug(handle).split("-"))
            hits = [k for k in sheets if k not in used and set(k.split("-")) <= words]
            if len(hits) == 1:
                with_text(sheets[hits[0]], item); used.add(hits[0])
                items.append(item)  # F02 lists only NPCs with their own npc-<name>.md sheet (Day-121 rule)
    for key, p in sorted(sheets.items()):                            # a sheet with no master-list row
        if key not in used:
            items.append(with_text(p, {"floor": "npc", "data": {"handle": h1(p).title(), "system": "RED", "status": "Active",
                                                                 "notes": "Character sheet (not on the master list's NPCs-in-play table)."}}))

    # ---------------------------------------------------------------- PC(s)
    for p in sorted(pk.glob("pc-*.md")):
        name = h1(p).title()                                       # 'Hakk "Slipstream"'
        handle = name.split()[0].strip('"')                         # 'Hakk' (the quoted part is the street name)
        items.append(with_text(p, {"floor": "pc", "data": {"handle": handle, "name": name, "system": "RED",
                                                           "status": "Active", "player": "Shane",
                                                           "notes": "The full character sheet is under Full text (the sheet wins over any other source)."}}))

    # ---------------------------------------------------------------- reference sheets
    def category(n):
        if n.startswith("cp-campaign-state-day-"): return "Campaign state"
        if n.startswith("cp-ref-architecture-"): return "Architecture"
        if n.startswith("cp-ref-vehicle-"): return "Vehicle"
        if n.startswith("cp-arc-"): return "Arc"
        if n.endswith("-master-list.md"): return "Master list"
        if re.search(r"-board\.md$|live-sites", n): return "Board"
        if re.search(r"bank-balances|world-stock-exchange|si-portfolio|wse-dividends|whitehat-business-mechanics", n): return "Financial"
        if n.startswith("cp-homebrew-"): return "House rule"
        if n in ("cp-deck-cerberus-build-sheet.md",): return "Character sheet"
        if n in ("cp-kickoff-script.md", "CHARACTER-SHEETS.md"): return "Rules"
        return "Reference"
    for p in sorted(pk.glob("*.md")):
        n = p.name
        if n in SKIP or SEALED.match(n) or n.startswith(("npc-", "pc-")):
            continue
        if not (n.startswith(("cp-", "canon-index", "CHARACTER-SHEETS"))):
            continue
        state = n.startswith("cp-campaign-state-day-")
        src = "cp-campaign-state-day-N.md (live board)" if state else n     # stable match key across days
        title = h1(p) if not state else "Campaign state — live board"
        body = desc.get(n) or desc.get("cp-campaign-state-day-[N].md" if state else n, "")
        if state:
            body = f"Opens Day {last_day + 1} (file {n}). " + body
        items.append(with_text(p, {"floor": "sheets", "match": "source", "data": {
            "title": title[:160], "category": category(n), "system": "RED", "source": src, "body": body}}))

    # ---------------------------------------------------------------- sources: manifest §4 -> sourcebooks / dlc
    names = {
        "Cyberpunk_RED_Corebook_text_only.md": ("Cyberpunk RED Core Rulebook (text)", "sourcebooks"),
        "cp-corebook-errata-v1_25.txt": ("Core Rulebook Errata v1.25", "dlc:Patch"),
        "cp-corebook-rules-locator.md": ("Core Rulebook rules locator", "sourcebooks"),
        "Netrunning-Deck-First-Printing-Errata.pdf": ("Netrunning Deck errata (first printing)", "dlc:Patch"),
        "cp-blackchrome-v1_0.md": ("Black Chrome v1.0", "dlc:Expansion"),
        "RTG-CPR-DLC-BlackChromePlusv1_21.md": ("Black Chrome+ v1.21", "dlc:Expansion"),
        "RTGCPRDLCNoPlaceLikeHome1.pdf": ("No Place Like Home", "dlc:Expansion"),
        "RTG-CPR-DLC-InventedTechUpgradesv1.1.md": ("Invented Tech Upgrades v1.1", "dlc:Expansion"),
        "RTG-CPR-DLC-DangerGalDossierPlus.md": ("Danger Gal Dossier and Dossier+", "dlc:Expansion"),
        "cp-night-city-2045-fulltext.md": ("Night City 2045 (full text)", "sourcebooks"),
        "cp-night-city-2045-district-index.md": ("Night City 2045 district index", "sourcebooks"),
        "RTG-CPR-DLC-NightCityAtlasv1.01.pdf": ("Night City Atlas v1.01", "sourcebooks"),
        "824017293NightCity2045AtlasFull1.pdf": ("Night City 2045 Atlas poster map", "sourcebooks"),
        "1002257734-RTG-CPR-DLC-NightMarketIndexv1-24.pdf": ("Night Market Index v1.24", "sourcebooks"),
        "RTG-CPR-DLC-RockerboyIndexv1.01.md": ("Rockerboy Index v1.01", "sourcebooks"),
        "cp-teranomicron-homebrew-v1.md": ("Teranomicron homebrew v1", "dlc:Homebrew"),
        "The-Vehicles-of-Red-Conversion-Guide-2_0.pdf": ("The Vehicles of RED conversion guide 2.0", "dlc:Homebrew"),
    }
    src_rows = list(table_rows(section(mlines, r"^## 4 ", r"^## 5 ")))
    for c in src_rows:
        if len(c) < 3 or c[0] == "File":
            continue
        files = re.findall(r"`([^`]+)`", c[0])
        if not files or any(f.startswith("CP_") for f in files):
            continue
        known = [f.split("/")[-1] for f in files if f.split("/")[-1].replace("claude/", "") in names]
        fn = known[0] if known else files[-1].split("/")[-1]
        where, what = plain(c[1]), plain(c[2])
        if fn.startswith("claude/"):
            fn = fn[7:]
        title, kind = names.get(fn, (None, None))
        if not title:                                       # a source this script doesn't know yet: catalogue it by folder
            if "Interface-RED" in fn: title, kind = "Interface RED Vols 1–5", "dlc:Expansion"
            elif "YourNewBestFriend" in fn: title, kind = "Your New Best Friend", "dlc:Expansion"
            elif "dlc/" in where: title, kind = fn, "dlc:Expansion"
            elif "homebrew/" in where: title, kind = fn, "dlc:Homebrew"
            elif "rules/" in where or "world/" in where: title, kind = fn, "sourcebooks"
            else:
                continue
        fmt = "PDF" if fn.lower().endswith(".pdf") else "Text"
        note = f"{what}\nWhere: {where} · file {fn}"
        if kind == "sourcebooks":
            add_src(fn, {"floor": "sourcebooks", "data": {"title": title, "system": "RED", "publisher": "R. Talsorian Games" if "RTG" in fn or "Corebook" in fn or "night-city" in fn.lower() or "NightCity" in fn else "",
                                                           "format": fmt, "status": "Owned", "notes": note}})
        else:
            add_src(fn, {"floor": "dlc", "data": {"title": title, "type": kind.split(":")[1], "status": "Active", "system": "RED",
                                                   "appliesTo": "Cyberpunk RED 2045 campaign", "notes": note}})

    # ---------------------------------------------------------------- campaign header
    camp = re.search(r"^#\s+(THE [A-Z ]+?)\s+—", manifest, re.M)
    items.append({"floor": "meta", "data": {"name": (camp.group(1).title() if camp else "Cyberpunk RED 2045"),
                                            "system": "RED", "session": str(last_day)}})

    # ---------------------------------------------------------------- write
    for it in items:  # the play day each PC/NPC sheet was filed for (labels its sheet-history version)
        if it['floor'] in ('pc', 'npc'):
            it['data']['asOfDay'] = last_day
    titles = {}
    for it in items:                                          # no two items may claim the same match key
        fl = it["floor"]; m = it.get("match", "handle" if fl in ("pc", "npc") else "title")
        k = (fl, str(it["data"].get(m, "")).lower()) if fl != "meta" else ("meta", "")
        if k in titles:
            die(f"two bundle items share {fl}:{it['data'].get(m)}")
        titles[k] = 1
    bundle = {"day": last_day, "packet": pk.name, "entries": items}
    (out / "bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = {}
    for it in items:
        counts[it["floor"]] = counts.get(it["floor"], 0) + 1
    tb = sum(f.stat().st_size for f in (out / "text").iterdir())
    print(f"[OK] {out}/bundle.json: " + ", ".join(f"{k} {v}" for k, v in counts.items()) + f"; full text {len(list((out / 'text').iterdir()))} files, {tb / 1048576:.1f} MB")
    print(f"     last closed day {last_day}; sealed files skipped: " + (", ".join(sorted(p.name for p in pk.glob('gm-arc-*'))) or "none"))


if __name__ == "__main__":
    main()
