# DATAFORT RUNBOOK — for Claude

How to file each Cyberpunk RED 2045 play day (entries, canon and files) into the NXROOT Datafort on hades, and how to change the site safely. Written for Claude. Follow it as written; when something here conflicts with what you find on the machine, stop and tell the owner instead of improvising.

Version 1.1 · 2026-11-17 · lives in the repo as `~/projects/payload/DATAFORT-RUNBOOK.md` and in the claude.ai Project.

---

## 0. The system at a glance

| What | Where |
|---|---|
| Datafort (5 floors + Canon) | http://localhost:8087/ |
| Finance dashboard | http://localhost:8087/finance |
| Payload admin | http://localhost:8087/admin (always `localhost`, not `127.0.0.1`) |
| Project (source of truth, git) | `~/projects/payload` → `git@github-iFeelNull:iFeelNull/CP2045.git` (private) |
| Stack | `~/projects/webstack-payload` (rootless podman-compose), containers `ws-payload-web`, `ws-payload-db` (Postgres 18) |
| Start/stop | `systemctl --user start\|stop\|restart webstack-payload.service` |
| Entries | Postgres table `entries` (floor + JSON `data`) — **not in git** |
| Images / PDFs | `~/projects/payload/media/datafort-images`, `media/datafort-files` — **not in git** |
| Ledger | `~/projects/payload/public/data/ledger.json` (in git); workbooks `*.xlsx` are git-ignored |
| Tools | `~/projects/payload/tools/datafort-sync.py`, `add_canon_floor.py`, `parse_ledger.py` |
| Backups | `~/backups/` (mode 700): `payload-db-*.dump` (pg_dump -Fc), `payload-pre-*.tar.gz` |
| Logs | `~/system-logs/` |
| Host / user | hades, RHEL 10.2, SELinux Enforcing, user `cerberus` |

Data model, one row per entry: `{ floor, data, owner }`. `floor` is one of `pc npc sheets sourcebooks dlc canon meta`. `data` is free-form JSON whose keys are the field keys in §8. Files are referenced from `data` as `pl:<collection>/<id>/<filename>`.

## 1. Rules (never break these)

1. **This site never leaves the laptop.** No hosting, deploy, domain, tunnel or cloud storage. Only the code goes to the private GitHub repo.
2. **Never type a password, passphrase or API key**, in a terminal or a form. The owner types them. Never print the API key (`cat` it, `echo` it, put it in a URL).
3. **Back up before writing.** `datafort-sync.py --apply` takes a `pg_dump` by itself; for anything else run the backup in §6.1 first.
4. **Dry run first.** Show the owner the plan; apply only after they agree.
5. **Canon is only what the day's close made canon.** File it from the close documents; never invent, embellish or "fill in". Uncertain → `status: "Rumor"` and say so. GM-only material goes in an NPC's `secrets` field, never in canon `body`.
6. **SELinux:** files copied into `~/projects/payload` from elsewhere arrive with the wrong label and the container gets `EACCES` (HTTP 500). Never `cp -a` or `mv` into the project; after copying, run `chcon -R --reference=$HOME/projects/payload <paths>`.
7. **Customer separation:** lcfrw is a paid customer site. Never touch `~/projects/lcfrw`, `webstack-lcfrw`, its token or its Render service from this runbook.
8. Don't change the stack (`webstack-payload/`), ports, firewalld, or the Payload/Next versions as part of a game day.

## 2. How Claude reaches hades

Claude works in its own cloud workspace. hades is reached only through **Claude in Chrome → Cockpit terminal**:

1. `tabs_context_mcp`; open or reuse the Claude-group tab at **http://localhost:9090/system/terminal** (`http`, not `https`: the cert isn't trusted for localhost).
2. If it shows a login page, **stop and ask the owner to log in**. Cockpit logs out when idle; expect to ask again after long pauses.
3. Click into the terminal, `type` one command line ending in `\n`, `wait`, then `zoom` on the terminal area to read output. Start commands with `clear;` and keep output short (`| tail -20`, `| cut -c1-150`). For long output, write it to a file and read it in pieces.
4. **Files from Claude's workspace → hades:** send with SendUserFile; the owner downloads it in Chrome on hades (lands in `~/Downloads`). Claude cannot push files to the laptop. Verify arrival and size: `ls -l ~/Downloads/<name>` against the size Claude built.
5. Unzip into a **fresh** folder (`rm -rf ~/datafort-days/day-X && mkdir -p …`), never over an old one.

## 3. One-time setup (do once; skip any step already done)

Check what's done:

```bash
clear; cd ~/projects/payload; grep -c 'key: "canon"' public/index.html; grep -c useAPIKey src/collections/Users.ts; grep -c 'String(row.id)' public/index.html; ls -l ~/.config/datafort/api-key tools/datafort-sync.py 2>&1 | cut -c1-90; cd ~
```

### 3.1 Theme v1.1 (fixes: clicking a list entry showed an empty detail pane)

Owner downloads `nxroot-datafort-2045.zip` (v1.1). Then:

```bash
clear; rm -rf ~/Downloads/datafort-theme && mkdir ~/Downloads/datafort-theme && unzip -q ~/Downloads/nxroot-datafort-2045.zip -d ~/Downloads/datafort-theme && cd ~/Downloads/datafort-theme/nxroot-datafort-2045 && ./install-datafort-theme.sh 2>&1 | tee ~/system-logs/install-datafort-theme-$(date +%Y%m%d-%H%M).log | tail -25; cd ~
```

It backs up, copies the overlay (incl. `tools/` and this runbook), fixes SELinux labels, restarts and verifies. Re-installing replaces `public/index.html` and `Users.ts`, so **always run 3.2 again after any re-install**.

### 3.2 Canon floor + API keys (searchable canon)

```bash
clear; cd ~/projects/payload && python3 tools/add_canon_floor.py . && chcon -R --reference=. public src/collections && systemctl --user restart webstack-payload.service; cd ~
```

Idempotent: prints `skip` for anything already there. The restart is needed because `Users.ts` (API keys) and the `floor` options changed; Payload's dev schema push adds the `canon` value and the API-key columns by itself (non-destructive). Wait ~1 minute, then check `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8087/admin` → `200`.

### 3.3 API key for scripted uploads (owner does the secret parts)

1. **Owner:** http://localhost:8087/admin → Users → their account → tick **Enable API Key** → copy the key → **Save**.
2. **Owner, in the terminal** (Claude may type the first line, the owner pastes the key and presses Enter, then Ctrl-D):
   ```bash
   install -d -m 700 ~/.config/datafort && ( umask 077; cat > ~/.config/datafort/api-key )
   ```
3. **Claude** checks without revealing it:
   ```bash
   clear; stat -c '%a %s' ~/.config/datafort/api-key; curl -s -H "Authorization: users API-Key $(cat ~/.config/datafort/api-key)" http://localhost:8087/api/users/me | grep -o '"email":"[^"]*"'
   ```
   Expect `600` and the owner's email. Entries filed with the key belong to that user, exactly as if they'd typed them.

### 3.4 Git (if not done yet)

`setup-payload-git.sh --user iFeelNull --repo CP2045 --email <owner's noreply address>` — the owner types the SSH key passphrase and adds the public key at github.com/settings/ssh/new (signed in as iFeelNull). The script refuses to push over a non-empty remote; if it says so, stop and ask.

## 4. Every game day

Run this **after** the day is closed with the `cp-close-day` skill (the close produces the canon). The day is X.

### 4.1 Gather the inputs (in Claude's workspace)

From the closed packet and close outputs, read:

- `cp-day-X-complete.md` (the day file, every part) and `cp-day-X-close.md`
- the canon index changes made at this close (`canon-index` in the packet)
- master-list rows for NPCs who appeared or changed; PC sheet changes (HP, Humanity, eddies, REP, IP, gear, status)
- handouts/PDFs the day produced; portraits if the owner supplied any
- the Slipstream accounts workbook for the day, if the owner attached one

If any of these is missing, ask for it; don't reconstruct it.

### 4.2 Build the bundle

Create `datafort-day-X/` with `bundle.json` and the files it references (relative paths). Schema in §7. Mapping:

| Source | Datafort entry |
|---|---|
| Each new or changed canon item | `floor: "canon"`: `title` (short, specific), `kind` (Event/Person/Place/Faction/Item/Ruling/Lore/Thread), `status` (Canon/Rumor/Retconned), `day: "X"`, `when` (in-game date), `tags` (comma list: names, factions, places), `summary` (1–2 sentences), `body` (the canon text as the close states it), `source` (`cp-day-X-complete.md §N`) |
| A canon item retconned today | same entry (same `title`), `status: "Retconned"`, body says what replaced it |
| The day file | `floor: "sheets"`: `title: "Day X — <day title>"`, `category: "Session log"`, `system: "RED"`, `body` = the day file text; attach a PDF via `files.file` if one exists |
| NPC appeared/changed | `floor: "npc"`, match `handle`, **merge**: only the changed fields (`disposition`, `status`, `location`, `notes`…). New NPC: `handle`, `affiliation`, `role`, `threat`, `disposition`, `status`. GM-only → `secrets` |
| PC changed | `floor: "pc"`, match `handle`, merge only changed fields (`hp`/`hpMax`, `hum`/`humMax`, `eddies`, `rep`, `ip`, `status`, `gear`…) |
| Campaign header | `floor: "meta"`: `session: "X"` (plus `name`, `gm`, `system` only if they change) |

Rules: one canon entry per fact or event, not one per day; keep `title` stable (it's the match key — changing it creates a new entry); never put a value you can't point to in the close documents.

Validate locally before sending: `python3 -c "import json;d=json.load(open('datafort-day-X/bundle.json'));print(len(d['entries']),'entries')"` and check every `files` path exists. Zip it: `zip -qr datafort-day-X.zip datafort-day-X`. Send with SendUserFile and ask the owner to download it on hades.

### 4.3 File it on hades (Cockpit terminal)

```bash
clear; ls -l ~/Downloads/datafort-day-X.zip; rm -rf ~/datafort-days/day-X && mkdir -p ~/datafort-days/day-X && unzip -q ~/Downloads/datafort-day-X.zip -d ~/datafort-days/day-X && python3 ~/projects/payload/tools/datafort-sync.py ~/datafort-days/day-X/datafort-day-X
```

That is the **dry run**: it lists `CREATE` / `UPDATE (fields…)` / `SAME` per item and changes nothing. Show the owner the plan. On their go:

```bash
clear; python3 ~/projects/payload/tools/datafort-sync.py ~/datafort-days/day-X/datafort-day-X --apply 2>&1 | tee ~/system-logs/datafort-day-X-$(date +%H%M).log | tail -25
```

It takes `~/backups/payload-db-pre-sync-dayX-*.dump` first and refuses to continue if the backup fails. Re-running is safe: unchanged items report `SAME`; a changed file replaces the old upload (the old one is deleted).

### 4.4 Ledger (only if a workbook came with the day)

The owner downloads the `.xlsx`; then:

```bash
clear; cd ~/projects/payload && cp ~/Downloads/Slipstream-Accounts-DayX.xlsx . && python3 tools/parse_ledger.py "Slipstream-Accounts-DayX.xlsx" public/data/ledger.json; echo "exit $?"; ls -Z public/data/ledger.json | cut -c1-80; cd ~
```

Exit 2 = a reconciliation mismatch: report the entity it names and stop; don't edit the workbook. The label must read `container_file_t:s0:c…`; if not, `chcon --reference=. public/data/ledger.json`. If `openpyxl` is missing: `pip install --user -r tools/requirements.txt` (the owner may need to approve).

### 4.5 Verify

- Browser: http://localhost:8087/ → Canon floor → search for a new title and one body phrase; open one entry and its PDF. `/finance` shows the new day if the ledger changed.
- Terminal: `clear; podman logs --since 10m ws-payload-web 2>&1 | grep -iE 'error|EACCES' | tail -5` → nothing.

### 4.6 Commit (code and ledger only; entries live in Postgres)

```bash
clear; cd ~/projects/payload && git status --short | head -20 && git add -A && git commit -q -m "Day X close: ledger + site changes" && git push 2>&1 | tail -3; cd ~
```

Skip if `git status` is empty. If the push asks for the key passphrase, the owner types it.

### 4.7 Report

Tell the owner: items created/updated/same, the backup file, ledger result, anything skipped and why. Keep the bundle zip; the owner files it with the day's packet in Drive.

## 5. Recover

- **Undo a sync:** `podman exec -i ws-payload-db pg_restore -U payload -d payload --clean --if-exists < ~/backups/payload-db-pre-sync-dayX-<ts>.dump` (owner's go first; it rolls back everything after that backup).
- **Undo a theme install:** `tar -xzf ~/backups/payload-pre-datafort-<ts>.tar.gz -C ~/projects/payload`, then §3.2 if canon was added, then restart.
- Uploaded files aren't in the dump; a restore can leave orphan files in `media/` (harmless).

## 6. Modifying the site

### 6.1 Ground rules

1. Backup first:
   ```bash
   clear; cd ~/projects/payload && TS=$(date +%Y%m%d-%H%M%S) && tar -czf ~/backups/payload-src-$TS.tar.gz src public next.config.ts tools && podman exec ws-payload-db pg_dump -U payload -Fc payload > ~/backups/payload-db-$TS.dump && chmod 600 ~/backups/*-$TS.*; ls -l ~/backups/*-$TS.*; cd ~
   ```
2. Edit in `~/projects/payload` only. Prefer a small, idempotent Python patch script (like `tools/add_canon_floor.py`: exact-anchor replace, assert the anchor occurs once, skip if already applied) over hand edits through the terminal. Build and test it in Claude's workspace against a copy of the same files first.
3. After writing files: `chcon -R --reference=. <changed paths>`.
4. What reloads by itself: `public/*` (refresh the browser) and most of `src/` (hot reload). What needs `systemctl --user restart webstack-payload.service`: `next.config.ts`, `payload.config.ts`, new or changed collections and access rules, `Users.ts`.
5. Schema: Payload dev mode **pushes** the schema to Postgres on start. Adding fields, collections or select options is safe. **Renaming or removing a field or option drops its column/data** — back up, and confirm with the owner. Datafort entry fields live inside the JSON `data` column, so page-only fields (§6.3) need no schema change at all.
6. Verify (§4.5), then commit (§4.6).

### 6.2 Where things live

| To change | Edit |
|---|---|
| A floor's fields, labels, search, list text | `public/index.html` → `const FLOORS = [...]` (one object per floor) |
| How an entry reads in the detail pane | `public/index.html` → `const READ = { <floor>(f, r) {...} }` — **every floor needs one** |
| Badge colours for status values | `public/index.html` → `const TONE` (`ok` / `warn` / `bad` / `dim`) |
| Search | `matches()` searches primary field, sub-line, `name`, badge, code, plus the floor's optional `search: r => [...]` list |
| Data access (save, load, uploads) | `public/index.html` → `const API` (Payload REST, same origin, cookie) |
| Allowed `floor` values | `src/collections/Entries.ts` → `floor` options (must include every `FLOORS[].key` + `meta`) |
| Who can see/change what | `src/collections/datafortAccess.ts` (owner-only) |
| Upload types / folders | `src/collections/DatafortUploads.ts` (`mimeTypes`, `staticDir`) |
| Upload size limit | `src/payload.config.ts` `upload.limits.fileSize` **and** `public/config.js` `maxFileMB` (keep equal) |
| Port / cookie origins | `src/payload.config.ts` `csrf` (or env `SITE_ORIGINS`) |
| URLs, security headers | `next.config.ts` (`rewrites`, `headers`); keep `connect-src 'self'` |
| Sync tool floors / match keys | `tools/datafort-sync.py` → `FLOORS` dict |

### 6.3 Worked example: the searchable Canon floor

`tools/add_canon_floor.py` is the reference implementation. What it does, in order (all five are needed for any new floor):

1. **Payload** — `Entries.ts`, allow the new floor value:
   ```ts
   { label: 'Canon', value: 'canon' },
   ```
2. **Floor definition** — append to `FLOORS` in `index.html`:
   ```js
   { key: "canon", code: "CAN", title: "Canon", short: "Canon", noun: "canon entry", newLabel: "Add canon", ph: "Search canon (full text)",
     desc: "What is true in this campaign …", empty: ["No canon filed", "…"],
     primary: "title",
     sub: r => [r.kind, r.day && "Day " + r.day], badge: r => r.status,
     chips: r => [r.kind, r.day && "Day " + r.day, r.when, ...String(r.tags || "").split(",").map(t => t.trim()).filter(Boolean)],
     search: r => [r.summary, r.body, r.tags, r.when, r.source, r.day && "day " + r.day],   // full-text search
     fields: [ { k: "title", label: "Title", type: "text", req: true }, { k: "kind", type: "select", opts: [...] , label: "Kind" }, … ] }
   ```
   Field types available: `text`, `url`, `select` (+`opts`), `textarea` (+`rows`, `mono`), `image`, `file`, `meter` (stores `k` and `kMax`), `stats`.
3. **Search** — `matches()` adds the floor's `search(r)` values to what it searches:
   ```js
   const hay = [r[f.primary], ...(f.sub(r) || []), r.name, f.badge(r), code(f, r), ...((f.search && f.search(r)) || [])]…
   ```
4. **Detail renderer** — add `READ.canon(f, r)` built from the helpers `headHTML`, `readouts`, `blockHTML`, `fileHTML`. Without it, opening an entry throws and the pane stays empty.
5. **Badge tones** — `TONE`: `Canon: "ok", Rumor: "warn", Retconned: "bad"`.

Plus: `Users.ts` gets `useAPIKey: true` (for §3.3), the ticker's floor count follows `FLOORS.length`, and `tools/datafort-sync.py` already knows `canon` (match key `title`).

### 6.4 Other recipes

- **Add a field to an existing floor:** add `{ k, label, type }` to that floor's `fields`, show it in its `READ` renderer (`readouts([...])` or `blockHTML(...)`), and add it to `search` if it should be searchable. No restart, no schema change.
- **Make another floor full-text searchable:** add `search: r => [r.notes, r.body, …]` to that floor.
- **Add a select option** (e.g. a new NPC status): edit the `opts` list; add a `TONE` entry if it's a badge.
- **Allow another attachment type** (e.g. `.zip` packets): add the MIME type to `DatafortFiles.mimeTypes`, the extension to the `accept=` and the magic-byte check in `API.uploadFile` (index.html), restart.
- **Another whole floor:** copy §6.3 steps 1–5 with a new key; add the key to `datafort-sync.py` `FLOORS` with its match field.
- **Never:** add a CDN script/font, widen `connect-src`, turn off `csrf`, make a collection's `read` public, or bind a port beyond 127.0.0.1.

## 7. `bundle.json` reference

```json
{
  "day": 112,
  "entries": [
    { "floor": "canon",
      "data": { "title": "Hakk buys the SI TEAB stake", "kind": "Event", "status": "Canon", "day": "112",
                "when": "Mon Oct 16, 2045", "tags": "Slipstream, TEAB, Hakk",
                "summary": "…", "body": "…", "source": "cp-day-112-complete.md §3" },
      "files": { "file": "handouts/teab-term-sheet.pdf" } },
    { "floor": "npc", "data": { "handle": "Aster Vale", "disposition": "Wary" },
      "files": { "portrait": "portraits/aster.png" } },
    { "floor": "pc", "data": { "handle": "Rogue", "status": "Injured", "eddies": "12,400" } },
    { "floor": "sheets", "data": { "title": "Day 112 — The Rollover", "category": "Session log", "system": "RED", "body": "…" } },
    { "floor": "meta", "data": { "session": "112" } }
  ]
}
```

- `match` (optional): the field that identifies an existing entry; default `handle` for pc/npc, `title` otherwise; `meta` is a single entry.
- `mode` (optional): `merge` (default, only the given fields change) or `replace`.
- `files`: `portrait` / `image` / `cover` → images (PNG/JPEG/GIF/WebP ≤ 10 MB); `file` → PDF/EPUB (≤ 100 MB; Payload rejects files that aren't real PDFs/EPUBs).
- The tool adds `seq` and `createdAt` to new entries, `updatedAt` on changes, and `<field>Name`/`<field>Size`/`<field>Src` for files.

## 8. Field keys per floor

| Floor | Key fields (match key first) |
|---|---|
| `pc` | **handle**, name, role, player, system, status (Active/Injured/Flatlined/Retired/MIA), hp/hpMax, hum/humMax, eddies, rep, ip, stats, skills, cyberware, gear, lifepath, notes, portrait |
| `npc` | **handle**, name, affiliation, role, location, threat (Mook/Lieutenant/Mini-Boss/Boss), disposition (Hostile/Wary/Neutral/Friendly/Ally), status (Active/Flatlined/Missing/Unknown), system, stats, abilities, notes, secrets, portrait |
| `sheets` | **title**, category (Rules/Table/Map/Handout/House rule/Session log/Other), system, link, file, image, body |
| `sourcebooks` | **title**, system, publisher, year, pages, format, file, status (Owned/Wishlist/Borrowed), link, notes, cover |
| `dlc` | **title**, type, status (Active/Planned/Disabled), system, appliesTo, released, file, link, notes |
| `canon` | **title**, kind, status (Canon/Rumor/Retconned), day, when, tags, summary, body, source, file |
| `meta` | name, gm, session, system (single entry) |

`system` values: 2020, 2030, RED, 2077, Other. Select values must match exactly (the page shows unknown values as blank).

## 9. Troubleshooting

| Symptom | Cause → fix |
|---|---|
| Admin page blank | Opened via `127.0.0.1` without `allowedDevOrigins` → use `http://localhost:8087/admin` |
| `/` or `/finance` HTTP 500, log shows `EACCES` | SELinux label → `chcon -R --reference=$HOME/projects/payload <path>` |
| Clicking a list entry shows an empty detail pane | Theme v1.0 (numeric ids) → install v1.1 (§3.1); or a floor without a `READ` renderer |
| `datafort-sync`: "API key was not accepted" | Key not saved in admin, or file wrong → §3.3 |
| `datafort-sync`: floor 'canon' → HTTP 400 | §3.2 not applied or stack not restarted |
| `datafort-sync`: "matches N existing entries" | Duplicate titles/handles → merge or rename them in /admin first |
| Datafort "Couldn't reach the Payload server" | Stack down → `systemctl --user status webstack-payload.service`, then `start` |
| Cockpit shows Disconnected / login | Idle timeout → owner logs in again |
| `parse_ledger.py` exit 2 | Reconciliation mismatch in the workbook → report the entity, stop |
